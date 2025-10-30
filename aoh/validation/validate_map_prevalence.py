# Implementation of AoH model validation from Dahal et al.
# Based on R code authored by Franchesca Ridley.

import argparse
from pathlib import Path

import pandas as pd

try:
    import pymer4 # type: ignore
except (ImportError, ValueError):
    pymer4 = None

def prepare_predictors(aoh_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate and standardize predictor variables."""
    # Calculate elevation metrics
    aoh_df['elevation_range'] = aoh_df['elevation_upper'] - aoh_df['elevation_lower']
    aoh_df['elevation_mid'] = (aoh_df['elevation_upper'] + aoh_df['elevation_lower']) / 2
    aoh_df['elevation_rangekm'] = aoh_df['elevation_range'] / 1000.0
    aoh_df['elevation_midkm'] = aoh_df['elevation_mid'] / 1000.0

    # Standardize predictors across full dataset
    means = aoh_df.mean(axis=0, numeric_only=True)
    standard_devs = aoh_df.std(axis=0, numeric_only=True)

    aoh_df['std_elevation_rangekm'] = (
        (aoh_df.elevation_rangekm - means.elevation_rangekm) / standard_devs.elevation_rangekm
    )
    aoh_df['std_elevation_midkm'] = (
        (aoh_df.elevation_midkm - means.elevation_midkm) / standard_devs.elevation_midkm
    )
    aoh_df['std_n_habitats'] = (
        (aoh_df.n_habitats - means.n_habitats) / standard_devs.n_habitats
    )

    return aoh_df

def add_diagnostic_columns(
    klass_df: pd.DataFrame,
    upper_fence: float,
    lower_fence: float,
    iqr: float
) -> pd.DataFrame:
    """Add all diagnostic columns to class dataframe."""
    # Calculate class means for comparison
    klass_means = klass_df[['elevation_rangekm', 'elevation_midkm', 'n_habitats', 'prevalence']].mean()

    # Outlier flags and type
    klass_df['outlier'] = (klass_df.residual > upper_fence) | (klass_df.residual < lower_fence)
    klass_df['outlier_type'] = 'normal'
    klass_df.loc[klass_df.residual < lower_fence, 'outlier_type'] = 'over-predicted'
    klass_df.loc[klass_df.residual > upper_fence, 'outlier_type'] = 'under-predicted'

    # Outlier severity - IQR distance
    klass_df['outlier_iqr_distance'] = 0.0
    over_mask = klass_df.residual > upper_fence
    under_mask = klass_df.residual < lower_fence
    klass_df.loc[over_mask, 'outlier_iqr_distance'] = (
        (klass_df.loc[over_mask, 'residual'] - upper_fence) / iqr
    )
    klass_df.loc[under_mask, 'outlier_iqr_distance'] = (
        (lower_fence - klass_df.loc[under_mask, 'residual']) / iqr
    )

    # Human-readable explanation
    klass_df['explanation'] = 'Within normal range'
    klass_df.loc[klass_df.outlier_type == 'under-predicted', 'explanation'] = (
        'Observed prevalence (' + klass_df['prevalence'].round(3).astype(str) +
        ') much higher than predicted (' + klass_df['predicted'].round(3).astype(str) + ')'
    )
    klass_df.loc[klass_df.outlier_type == 'over-predicted', 'explanation'] = (
        'Observed prevalence (' + klass_df['prevalence'].round(3).astype(str) +
        ') much lower than predicted (' + klass_df['predicted'].round(3).astype(str) + ')'
    )

    # Flag extreme characteristics (>2 SD)
    klass_df['extreme_elevation_range'] = klass_df['std_elevation_rangekm'].abs() > 2
    klass_df['extreme_elevation_mid'] = klass_df['std_elevation_midkm'].abs() > 2
    klass_df['extreme_n_habitats'] = klass_df['std_n_habitats'].abs() > 2

    # Context comparison - percentage difference from class mean
    klass_df['elevation_range_vs_class_mean'] = (
        ((klass_df['elevation_rangekm'] - klass_means['elevation_rangekm']) /
         klass_means['elevation_rangekm'] * 100).round(1).astype(str) + '%'
    )
    klass_df['elevation_mid_vs_class_mean'] = (
        ((klass_df['elevation_midkm'] - klass_means['elevation_midkm']) /
         klass_means['elevation_midkm'] * 100).round(1).astype(str) + '%'
    )
    klass_df['n_habitats_vs_class_mean'] = (
        ((klass_df['n_habitats'] - klass_means['n_habitats']) /
         klass_means['n_habitats'] * 100).round(1).astype(str) + '%'
    )
    klass_df['prevalence_vs_class_mean'] = (
        ((klass_df['prevalence'] - klass_means['prevalence']) /
         klass_means['prevalence'] * 100).round(1).astype(str) + '%'
    )

    return klass_df

def fit_class_model(klass_df: pd.DataFrame, class_name: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fit model for a single taxonomic class and return diagnostics."""
    print(f"{class_name}:\n\taohs: {len(klass_df)}")

    # Fit the mixed model
    model = pymer4.Lmer(
        "prevalence ~ std_elevation_rangekm + std_elevation_midkm + std_n_habitats + (1|family_name)",
        data=klass_df,
        family="binomial"
    )
    model.fit()

    # Store fixed effect coefficients
    coef_df = model.coefs.copy()
    coef_df['class_name'] = class_name

    # Extract random effects for each family
    ranef_df = model.ranef.copy()
    ranef_df['class_name'] = class_name
    ranef_df = ranef_df.reset_index()
    # pymer4 uses 'X.Intercept.' as the column name for random intercepts
    intercept_col = [col for col in ranef_df.columns if 'Intercept' in col][0]
    ranef_df = ranef_df.rename(columns={'index': 'family_name', intercept_col: 'random_effect'})

    # Add predictions and residuals
    klass_df['predicted'] = model.fits
    klass_df['residual'] = klass_df['prevalence'] - klass_df['predicted']

    # Calculate outlier boundaries
    q1 = klass_df.residual.quantile(q=0.25)
    q3 = klass_df.residual.quantile(q=0.75)
    iqr = q3 - q1
    lower_fence = q1 - (1.5 * iqr)
    upper_fence = q3 + (1.5 * iqr)

    # Add all diagnostic columns
    klass_df = add_diagnostic_columns(klass_df, upper_fence, lower_fence, iqr)

    # Report outliers
    n_outliers = klass_df.outlier.sum()
    print(f"\toutliers: {n_outliers}")

    return klass_df, coef_df, ranef_df

def model_validation(aoh_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run model validation across all taxonomic classes."""
    if pymer4 is None:
        raise ImportError("pymer4 is required for model validation but not installed. "
                         "This requires R to be installed on the system.")

    # Filter out species with no AOH
    aoh_df = aoh_df[aoh_df.prevalence > 0].copy()

    # Prepare predictor variables
    aoh_df = prepare_predictors(aoh_df)

    # Get unique taxonomic classes
    klasses = aoh_df.class_name.unique()
    if len(klasses) == 0:
        raise ValueError("No species classes were found")

    # Fit models for each class
    all_species_list = []
    all_coefficients = []
    all_random_effects = []

    for klass in klasses:
        klass_df = aoh_df[aoh_df.class_name == klass].copy()
        klass_df, coef_df, ranef_df = fit_class_model(klass_df, klass)
        all_species_list.append(klass_df)
        all_coefficients.append(coef_df)
        all_random_effects.append(ranef_df)

    # Concatenate results
    all_species_df = pd.concat(all_species_list)  # type: ignore[arg-type]
    coefficients_df = pd.concat(all_coefficients)  # type: ignore[arg-type]
    random_effects_df = pd.concat(all_random_effects)  # type: ignore[arg-type]
    outliers_df = all_species_df[all_species_df.outlier == True]  # type: ignore[arg-type] # pylint: disable = C0121

    return outliers_df, all_species_df, coefficients_df, random_effects_df

def generate_readme(output_dir: Path, aoh_df: pd.DataFrame, outliers: pd.DataFrame) -> None:
    """Generate a README.md explaining the validation outputs."""

    # Count species by class
    class_counts = aoh_df.groupby('class_name').size().to_dict()
    outlier_counts = outliers.groupby('class_name').size().to_dict()

    # Count no AOH species
    no_aoh_count = len(aoh_df[aoh_df.aoh_total == 0])

    readme_content = f"""# Model Validation Results

This directory contains the results of the AoH prevalence model validation based on Dahal et al.

## Summary Statistics

- **Total species analyzed**: {len(aoh_df[aoh_df.aoh_total > 0])}
- **Species with no AOH**: {no_aoh_count}
- **Total outliers detected**: {len(outliers)}

### Species by Taxonomic Class

"""

    for class_name in sorted(class_counts.keys()):
        total = class_counts.get(class_name, 0)
        outlier_count = outlier_counts.get(class_name, 0)
        outlier_pct = (outlier_count / total * 100) if total > 0 else 0
        readme_content += f"- **{class_name}**: {total} species, {outlier_count} outliers ({outlier_pct:.1f}%)\n"

    readme_content += """
## Output Files

### 1. outliers.csv
Species identified as outliers based on their model residuals (±1.5 IQR from quartiles).

**Key columns:**
- `outlier_type`: Classification as 'over-predicted' (model overestimates prevalence) or 'under-predicted' (model underestimates)
- `explanation`: Human-readable description of why this species is an outlier
- `outlier_iqr_distance`: Severity metric - how many IQRs beyond the fence (higher = more extreme)
- `residual`: Difference between observed and predicted prevalence
- `predicted`: Model's predicted prevalence value

**Unusual characteristics (extreme predictor values, >2 SD from mean):**
- `extreme_elevation_range`: Boolean - unusually large/small elevation range
- `extreme_elevation_mid`: Boolean - unusually high/low elevation midpoint
- `extreme_n_habitats`: Boolean - unusually many/few habitats

**Context comparison (% difference from class mean):**
- `elevation_range_vs_class_mean`: Elevation range compared to class average
- `elevation_mid_vs_class_mean`: Elevation midpoint compared to class average
- `n_habitats_vs_class_mean`: Number of habitats compared to class average
- `prevalence_vs_class_mean`: Prevalence compared to class average

### 2. diagnostics.csv
Complete model diagnostics for ALL species (not just outliers). Contains the same diagnostic columns as outliers.csv but for the full dataset.

**Key columns:**
- `predicted`: Model's predicted prevalence
- `residual`: Observed - predicted prevalence
- `outlier`: Boolean flag for outlier status
- `outlier_type`: Classification (normal/over-predicted/under-predicted)
- `explanation`: Human-readable description
- `outlier_iqr_distance`: Severity metric (0 for non-outliers)
- Extreme predictor flags and class comparison percentages (same as outliers.csv)

### 3. coefficients.csv
Model coefficient estimates for each taxonomic class (simplified pivot table).

**Format:**
- Rows: Taxonomic classes (AMPHIBIA, AVES, MAMMALIA, REPTILIA)
- Columns: Model variables (Intercept and the three predictors)
- Values: Coefficient estimates from the binomial GLMM

### 4. random_effects.csv
Random effect estimates for each taxonomic family within each class.

**Key columns:**
- `family_name`: Taxonomic family
- `random_effect`: Deviation from class-level fixed effects (on logit scale)
- `class_name`: Taxonomic class

Random effects represent family-specific adjustments that account for phylogenetic clustering. Positive values indicate families with systematically higher prevalence than predicted by fixed effects alone.

### 5. no_aoh.csv
Species where the AOH calculation resulted in zero area. These are excluded from the model validation.

## Model Description

The validation uses a generalized linear mixed model (GLMM) with:
- **Response variable**: AOH prevalence (aoh_total / range_total)
- **Predictors**:
  - Elevation range (standardized)
  - Elevation midpoint (standardized)
  - Number of habitats (standardized)
- **Random effect**: Family (to account for phylogenetic clustering)
- **Family**: Binomial with logit link

Outliers are identified using the interquartile range (IQR) method on model residuals.
"""

    with open(output_dir / "README.md", 'w') as f:
        f.write(readme_content)

def validate_map_prevalence(
    collated_data_path: Path,
    output_path: Path,
) -> None:
    aoh_df = pd.read_csv(collated_data_path)

    # Create output directory
    output_dir = output_path.parent / "model_validation"
    output_dir.mkdir(exist_ok=True)

    # Save species with no AOH
    no_aoh = aoh_df[aoh_df.aoh_total == 0]
    no_aoh.to_csv(output_dir / "no_aoh.csv", index=False)

    outliers, all_species, coefficients, random_effects = model_validation(aoh_df)

    # Remove irrelevant columns from diagnostics
    columns_to_remove = ['threats', 'category_weight', 'assessment_year']
    diagnostics = all_species.drop(columns=[col for col in columns_to_remove if col in all_species.columns])

    # Simplify coefficients table - pivot to have classes as rows and variables as columns
    coefficients_simplified = coefficients.reset_index()
    coefficients_simplified = coefficients_simplified.rename(columns={'index': 'variable'})

    # Create estimates table
    estimates_pivot = coefficients_simplified.pivot(
        index='class_name',
        columns='variable',
        values='Estimate'
    )

    # Save the four main outputs
    outliers.to_csv(output_dir / "outliers.csv", index=False)
    diagnostics.to_csv(output_dir / "diagnostics.csv", index=False)
    estimates_pivot.to_csv(output_dir / "coefficients.csv", index=True)
    random_effects.to_csv(output_dir / "random_effects.csv", index=False)

    # Generate README
    generate_readme(output_dir, aoh_df, outliers)

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate map prevalence.")
    parser.add_argument(
        '--collated_aoh_data',
        type=Path,
        help="CSV containing collated AoH data",
        required=True,
        dest="collated_data_path"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        dest="output_path",
        help="CSV of outliers."
    )
    args = parser.parse_args()

    validate_map_prevalence(
        args.collated_data_path,
        args.output_path,
    )

if __name__ == "__main__":
    main()
