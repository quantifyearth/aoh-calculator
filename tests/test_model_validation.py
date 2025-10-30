"""
Tests for AOH prevalence model validation with random effects.

Key verification: Random effects can be extracted and used to reconstruct predictions,
proving we're not working backwards from fitted values.
"""

import math
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import pytest

try:
    import pymer4  # type: ignore # noqa: F401
    PYMER4_AVAILABLE = True
except (ImportError, ValueError):
    PYMER4_AVAILABLE = False

from aoh.validation.validate_map_prevalence import (
    fit_class_model,
    prepare_predictors,
    validate_map_prevalence,
)


@pytest.fixture
def synthetic_model_validation_data():
    """Generate synthetic data for model validation testing."""
    np.random.seed(42)

    # Create 60 species across 3 families
    families = ['FAMILY_A', 'FAMILY_B', 'FAMILY_C']
    n_per_family = 20

    data = []
    species_id = 1

    for family in families:
        for i in range(n_per_family):
            # Generate realistic variation in elevation and habitat
            elevation_lower = np.random.randint(0, 2000)
            elevation_range = np.random.randint(500, 4000)
            elevation_upper = elevation_lower + elevation_range
            n_habitats = np.random.randint(1, 6)

            # Generate range and AOH
            range_total = np.random.uniform(100, 10000)
            # Prevalence varies with elevation range and habitats (simulate realistic pattern)
            base_prevalence = 0.3 + (elevation_range / 10000) * 0.4 + (n_habitats / 10) * 0.2
            noise = np.random.normal(0, 0.1)
            prevalence = np.clip(base_prevalence + noise, 0.05, 0.95)
            aoh_total = range_total * prevalence

            data.append({
                'id_no': species_id,
                'assessment_id': 1000000 + species_id,
                'class_name': 'AMPHIBIA',
                'family_name': family,
                'scientific_name': f'Species {family.lower()} {i+1}',
                'full_habitat_code': '1.6',
                'category': 'EN',
                'season': 'all',
                'elevation_upper': elevation_upper,
                'elevation_lower': elevation_lower,
                'range_total': range_total,
                'hab_total': range_total,
                'dem_total': range_total,
                'aoh_total': aoh_total,
                'prevalence': prevalence,
                'assessment_year': 2020,
                'systems': 'Terrestrial',
                'threats': '[["1.1", 9]]',
                'category_weight': 300,
                'n_habitats': n_habitats,
            })
            species_id += 1

    return pd.DataFrame(data)


@pytest.mark.skipif(not PYMER4_AVAILABLE, reason="pymer4 not available")
def test_model_prepare_predictors(synthetic_model_validation_data):
    """Test that prepare_predictors correctly calculates and standardizes variables."""
    df = synthetic_model_validation_data.copy()
    df_prepared = prepare_predictors(df)

    # Check that new columns are created
    assert 'elevation_range' in df_prepared.columns
    assert 'elevation_mid' in df_prepared.columns
    assert 'elevation_rangekm' in df_prepared.columns
    assert 'elevation_midkm' in df_prepared.columns
    assert 'std_elevation_rangekm' in df_prepared.columns
    assert 'std_elevation_midkm' in df_prepared.columns
    assert 'std_n_habitats' in df_prepared.columns

    # Check calculations are correct for first row
    row = df_prepared.iloc[0]
    expected_range = row['elevation_upper'] - row['elevation_lower']
    assert abs(row['elevation_range'] - expected_range) < 0.001

    # Check standardization (mean ~ 0, std ~ 1)
    assert abs(df_prepared['std_elevation_rangekm'].mean()) < 0.1
    assert abs(df_prepared['std_elevation_rangekm'].std() - 1.0) < 0.1


@pytest.mark.skipif(not PYMER4_AVAILABLE, reason="pymer4 not available")
def test_model_fit_class(synthetic_model_validation_data):
    """Test that fit_class_model runs and returns correct structure."""
    df = synthetic_model_validation_data.copy()
    df = prepare_predictors(df)

    diagnostics_df, coef_df, ranef_df = fit_class_model(df, 'AMPHIBIA')

    # Check diagnostics has all rows and new columns
    assert len(diagnostics_df) == len(df)
    assert 'predicted' in diagnostics_df.columns
    assert 'residual' in diagnostics_df.columns
    assert 'outlier' in diagnostics_df.columns
    assert 'outlier_type' in diagnostics_df.columns

    # Check coefficients structure
    assert len(coef_df) == 4  # Intercept + 3 predictors
    assert 'Estimate' in coef_df.columns
    assert 'class_name' in coef_df.columns
    assert coef_df['class_name'].iloc[0] == 'AMPHIBIA'

    # Check random effects structure
    assert len(ranef_df) == 3  # 3 families in synthetic data
    assert 'family_name' in ranef_df.columns
    assert 'random_effect' in ranef_df.columns
    assert 'class_name' in ranef_df.columns
    assert set(ranef_df['family_name']) == {'FAMILY_A', 'FAMILY_B', 'FAMILY_C'}


@pytest.mark.skipif(not PYMER4_AVAILABLE, reason="pymer4 not available")
def test_model_prediction_reconstruction(synthetic_model_validation_data):
    """
    Verify predictions can be manually reconstructed from coefficients and random effects.

    This is the critical test proving the model outputs are mathematically consistent.
    """
    df = synthetic_model_validation_data.copy()
    df = prepare_predictors(df)

    diagnostics_df, coef_df, ranef_df = fit_class_model(df, 'AMPHIBIA')

    # Extract coefficients
    coef_dict = coef_df.set_index(coef_df.index)['Estimate'].to_dict()
    intercept = coef_dict['(Intercept)']
    beta_range = coef_dict['std_elevation_rangekm']
    beta_mid = coef_dict['std_elevation_midkm']
    beta_habitats = coef_dict['std_n_habitats']

    # Extract random effects
    ranef_lookup = ranef_df.set_index('family_name')['random_effect'].to_dict()

    # Test reconstruction for all species
    for _, row in diagnostics_df.iterrows():
        # Calculate fixed effects
        logit_fixed = (
            intercept +
            beta_range * row['std_elevation_rangekm'] +
            beta_mid * row['std_elevation_midkm'] +
            beta_habitats * row['std_n_habitats']
        )

        # Add family random effect
        logit_total = logit_fixed + ranef_lookup[row['family_name']]

        # Convert to probability
        predicted_manual = 1 / (1 + math.exp(-logit_total))
        predicted_model = row['predicted']

        # Must match within floating point precision
        assert abs(predicted_manual - predicted_model) < 1e-6, (
            f"Prediction mismatch for {row['scientific_name']}: "
            f"manual={predicted_manual:.10f}, model={predicted_model:.10f}"
        )


@pytest.mark.skipif(not PYMER4_AVAILABLE, reason="pymer4 not available")
def test_model_validation_pipeline(synthetic_model_validation_data):
    """Test the full model validation pipeline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Prepare input
        input_csv = tmpdir_path / "input.csv"
        synthetic_model_validation_data.to_csv(input_csv, index=False)

        # Run validation
        output_csv = tmpdir_path / "outliers.csv"
        validate_map_prevalence(input_csv, output_csv)

        # Check all expected files are created
        output_dir = tmpdir_path / "model_validation"
        assert (output_dir / "outliers.csv").exists()
        assert (output_dir / "diagnostics.csv").exists()
        assert (output_dir / "coefficients.csv").exists()
        assert (output_dir / "random_effects.csv").exists()
        assert (output_dir / "no_aoh.csv").exists()
        assert (output_dir / "README.md").exists()

        # Verify random_effects.csv structure
        ranef_df = pd.read_csv(output_dir / "random_effects.csv")
        assert len(ranef_df) == 3  # 3 families
        assert set(ranef_df['family_name']) == {'FAMILY_A', 'FAMILY_B', 'FAMILY_C'}
        assert ranef_df['random_effect'].dtype in [float, 'float64']
        assert not ranef_df['random_effect'].isna().any()

        # Verify coefficients.csv structure
        coef_df = pd.read_csv(output_dir / "coefficients.csv")
        assert 'class_name' in coef_df.columns
        assert 'AMPHIBIA' in coef_df['class_name'].values
        assert '(Intercept)' in coef_df.columns
        assert 'std_elevation_rangekm' in coef_df.columns
