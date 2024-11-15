# Based on R code authored by Franchesca Ridley.

import argparse

import pandas as pd
import statsmodels.formula.api as smf

def validate_map_prevalence(
    collated_data_path: str,
    output_path: str,
) -> None:
    aoh_df = pd.read_csv(collated_data_path)

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

    formula = smf.mixedlm(
        "prevalence ~ std_elevation_rangekm + std_elevation_midkm + std_n_habitats",
        data=aoh_df, groups=aoh_df["family_name"]
    )

    model = formula.fit()
    # model = formula.fit(method=["lbfgs"])
    # model = logit("prevalence ~ std_elevation_rangekm + std_elevation_midkm + std_n_habitats + family_name",
    # data=aoh_df).fit()

    aoh_df['fit'] = model.fittedvalues
    aoh_df['resid'] = model.resid
    aoh_df['fit_diff'] = aoh_df['prevalence'] - aoh_df['fit']

    q1 = aoh_df.fit_diff.quantile(q=0.25)
    q3 = aoh_df.fit_diff.quantile(q=0.75)
    iqr = q3 - q1

    aoh_df['outlier'] = (aoh_df.fit_diff > q3 + (1.5 * iqr))  | (aoh_df.fit_diff < (q1 - (1.5 * iqr)))

    outliers = aoh_df[aoh_df.outlier is True]
    outliers.to_csv(output_path)

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate map prevalence.")
    parser.add_argument(
        '--collated_aoh_data',
        type=str,
        help="CSV containing collated AoH data",
        required=True,
        dest="collated_data_path"
    )
    parser.add_argument(
        "--output",
        type=str,
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
