# Implementation of AoH model validation from Dahal et al.
# Based on R code authored by Franchesca Ridley.

import argparse
from pathlib import Path

import pandas as pd

try:
    import pymer4 # type: ignore
except (ImportError, ValueError):
    pymer4 = None

def model_validation(aoh_df: pd.DataFrame) -> pd.DataFrame:
    if pymer4 is None:
        raise ImportError("pymer4 is required for model validation but not installed. "
                         "This requires R to be installed on the system.")

    # Ger rid of any where we had no AoH
    aoh_df = aoh_df[aoh_df.prevalence > 0]

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

    per_class_df = []

    klasses = aoh_df.class_name.unique()
    if len(klasses) == 0:
        raise ValueError("No species classes were found")

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

        klass_df['outlier'] = (klass_df.fit_diff > q3 + (1.5 * iqr))  | (klass_df.fit_diff < (q1 - (1.5 * iqr)))
        klass_outliers = klass_df[klass_df.outlier == True]  # pylint: disable = C0121
        print(f"\toutliers: {len(klass_outliers)}")
        per_class_df.append(klass_outliers)

    return pd.concat(per_class_df)  # type: ignore[no-any-return]

def validate_map_prevalence(
    collated_data_path: Path,
    output_path: Path,
) -> None:
    aoh_df = pd.read_csv(collated_data_path)
    outliers = model_validation(aoh_df)
    outliers.to_csv(output_path)

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
