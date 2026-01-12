# Implementation of AoH model validation from Dahal et al.
# Based on R code authored by Franchesca Ridley.

import argparse
from pathlib import Path
from typing import cast

import pandas as pd

try:
    import pymer4 # type: ignore
except (ImportError, ValueError):
    pymer4 = None

def generate_results_summary(aoh_df: pd.DataFrame, outliers: pd.DataFrame) -> str:
    summary_content = (
        "# Model Validation Results Summary\n\n"
        + "## Summary Statistics\n\n"
        + f"- **Total species analyzed**: {len(aoh_df[aoh_df.aoh_total > 0])}\n"
        + f"- **Species with no AOH**: {len(aoh_df[aoh_df.aoh_total == 0])}\n"
        + f"- **Total outliers detected**: {len(outliers)}\n\n"
        + "## Species by Taxonomic Class\n"
    )

    # Count species by class
    class_counts = cast(dict[str,int], aoh_df.groupby('class_name').size().to_dict())
    outlier_counts = outliers.groupby('class_name').size().to_dict()

    for class_name in sorted(class_counts.keys()):
        total = class_counts.get(class_name, 0)
        outlier_count = outlier_counts.get(class_name, 0)
        outlier_pct = (outlier_count / total * 100) if total > 0 else 0
        summary_content += f"- **{class_name}**: {total} species, {outlier_count} outliers ({outlier_pct:.1f}%)\n"

    return summary_content

def add_diagnostic_columns(
    klass_df: pd.DataFrame,
    upper_fence: float,
    lower_fence: float
) -> pd.DataFrame:
    # Calculate class means for comparison
    klass_means = klass_df[['elevation_rangekm', 'elevation_midkm', 'n_habitats', 'prevalence']].mean()

    # Outlier flags and type
    klass_df['outlier_type'] = 'normal'
    klass_df.loc[klass_df.fit_diff < lower_fence, 'outlier_type'] = 'over-predicted'
    klass_df.loc[klass_df.fit_diff > upper_fence, 'outlier_type'] = 'under-predicted'

    # Human-readable explanation
    klass_df['explanation'] = 'Within normal range'
    klass_df.loc[klass_df.outlier_type == 'under-predicted', 'explanation'] = (
        'Observed prevalence (' + klass_df['prevalence'].round(3).astype(str) +
        ') much higher than predicted (' + klass_df['fit'].round(3).astype(str) + ')'
    )
    klass_df.loc[klass_df.outlier_type == 'over-predicted', 'explanation'] = (
        'Observed prevalence (' + klass_df['prevalence'].round(3).astype(str) +
        ') much lower than predicted (' + klass_df['fit'].round(3).astype(str) + ')'
    )

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

def extract_model_coefficients(model: "pymer4.models.Lmer", class_name: str) -> pd.DataFrame:
    coef_df = model.coefs.copy()
    # Normalize to have explicit variable column for easier downstream pivoting
    coef_df = coef_df.reset_index().rename(columns={'index': 'variable'})
    coef_df['class_name'] = class_name
    return coef_df

def extract_random_effects(model: "pymer4.models.Lmer", class_name: str) -> pd.DataFrame:
    ranef_df = model.ranef.copy()
    ranef_df['class_name'] = class_name
    ranef_df = ranef_df.reset_index()
    # pymer4 uses 'X.Intercept.' as the column name for random intercepts
    intercept_col = [col for col in ranef_df.columns if 'Intercept' in col][0]
    ranef_df = ranef_df.rename(columns={'index': 'family_name', intercept_col: 'random_effect'})
    return ranef_df

def add_predictors_to_aoh_df(aoh_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate and standardize predictor variables."""

    aoh_df['elevation_range'] = aoh_df['elevation_upper'] - aoh_df['elevation_lower']
    aoh_df['elevation_mid'] = (aoh_df['elevation_upper'] + aoh_df['elevation_lower']) / 2

    aoh_df['elevation_rangekm'] = aoh_df['elevation_range'] / 1000.0
    aoh_df['elevation_midkm'] = aoh_df['elevation_mid'] / 1000.0

    means = aoh_df.mean(axis=0, numeric_only=True)
    standard_devs = aoh_df.std(axis=0, numeric_only=True)

    aoh_df['std_elevation_rangekm'] = (aoh_df.elevation_rangekm - means.elevation_rangekm) \
        / standard_devs.elevation_rangekm
    aoh_df['std_elevation_midkm'] = (aoh_df.elevation_midkm - means.elevation_midkm) \
        / standard_devs.elevation_midkm
    aoh_df['std_n_habitats'] = (aoh_df.n_habitats - means.n_habitats) \
        / standard_devs.n_habitats

    return aoh_df

def model_validation(aoh_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if pymer4 is None:
        raise ImportError("pymer4 is required for model validation but not installed. "
                         "This requires R to be installed on the system.")

    # Get rid of any where we had no AoH
    aoh_df = aoh_df[aoh_df.prevalence > 0].copy()

    # Prepare predictor variables
    aoh_df = add_predictors_to_aoh_df(aoh_df)

    # Get unique taxonomic classes
    klasses = aoh_df.class_name.unique()
    if len(klasses) == 0:
        raise ValueError("No species classes were found")

    # Fit models for each class
    per_class_outliers_df = []
    per_class_model_coefficients = []
    per_class_random_effects = []

    for klass in klasses:
        klass_df = aoh_df[aoh_df.class_name == klass].copy()
        print(f"{klass}:\n\taohs: {len(klass_df)}")
        model = pymer4.Lmer(
            "prevalence ~ std_elevation_rangekm + std_elevation_midkm + std_n_habitats + (1|family_name)",
            data=klass_df,
            family="binomial"
        )
        model.fit()
        klass_df['fit'] = model.fits
        klass_df['fit_diff'] = klass_df['prevalence'] - klass_df['fit']

        q1 = klass_df.fit_diff.quantile(q=0.25)
        q3 = klass_df.fit_diff.quantile(q=0.75)
        iqr = q3 - q1
        lower_fence = q1 - (1.5 * iqr)
        upper_fence = q3 + (1.5 * iqr)

        klass_df['outlier'] = (klass_df.fit_diff > upper_fence )  | (klass_df.fit_diff < lower_fence )
        klass_df = add_diagnostic_columns(klass_df, upper_fence, lower_fence)
        klass_outliers = klass_df[klass_df.outlier == True]  # pylint: disable = C0121
        print(f"\toutliers: {len(klass_outliers)}")
        per_class_outliers_df.append(klass_outliers)

        coef_df = extract_model_coefficients(model, klass)
        per_class_model_coefficients.append(coef_df)

        ranef_df = extract_random_effects(model, klass)
        per_class_random_effects.append(ranef_df)

    # Concatenate results
    outliers_df = pd.concat(per_class_outliers_df)  # type: ignore[arg-type]
    model_coefficients_df = pd.concat(per_class_model_coefficients)  # type: ignore[arg-type]
    random_effects_df = pd.concat(per_class_random_effects)  # type: ignore[arg-type]

    return outliers_df, model_coefficients_df, random_effects_df

def validate_map_prevalence(
    collated_data_path: Path,
    output_path: Path,
) -> None:
    aoh_df = pd.read_csv(collated_data_path)
    outliers, model_coefficients, random_effects = model_validation(aoh_df)
    outliers.to_csv(output_path, index=False)

    # Save useful model diagnostic files
    output_dir = output_path.parent
    aoh_df[aoh_df.aoh_total == 0].to_csv(output_dir / "species_with_no_aoh.csv", index=False)
    model_coefficients.pivot(
        index='class_name', columns='variable', values='Estimate'
    ).to_csv(output_dir / "model_coefficients.csv", index=True)
    random_effects.to_csv(output_dir / "random_effects.csv", index=False)
    with open(output_dir / "summary.md", 'w', encoding='utf-8') as f:
        summary_content = generate_results_summary(aoh_df, outliers)
        f.write(summary_content)

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
