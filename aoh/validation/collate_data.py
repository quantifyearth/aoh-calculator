import argparse
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path

import pandas as pd

COLUMNS = [
    "id_no",
    "assessment_id",
    "assessment_year",
    "class_name",
    "family_name",
    "scientific_name",
    "full_habitat_code",
    "category",
    "season",
    "elevation_upper",
    "elevation_lower",
    "range_total",
    "hab_total",
    "dem_total",
    "aoh_total",
    "prevalence",
]

def collate_data(
    aoh_results: Path,
    output_path: Path,
) -> None:
    # Casting to a list here is a bit wasteful, but I think getting a sense
    # that there is no files early leads to better error reporting.
    manifests = list(aoh_results.glob("**/*.json"))
    if len(manifests) == 0:
        raise FileNotFoundError(f"Found no manifests in {aoh_results}")

    os.makedirs(output_path.parent, exist_ok=True)

    res = []
    all_keys = set()
    for manifest in manifests:
        with open(manifest, encoding="utf-8") as f:
            data = json.load(f)
            all_keys |= set(data.keys())
    assert set(COLUMNS).issubset(all_keys)

    keys = COLUMNS + list(all_keys - set(COLUMNS))
    for manifest in manifests:
        with open(manifest, encoding="utf-8") as f:
            data = json.load(f)
            row = []
            for k in keys:
                row.append(data.get(k, ''))
            row.append(len(data['full_habitat_code'].split('|')))
            res.append(row)
    df = pd.DataFrame(res, columns=keys + ['n_habitats'])
    df.to_csv(output_path, index=False)

def main() -> None:
    parser = argparse.ArgumentParser(description="Collate metadata from AOH build.")
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {version("aoh")}'
    )
    parser.add_argument(
        '--aoh_results',
        type=Path,
        help="Path of all the AoH outputs.",
        required=True,
        dest="aohs_path"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        dest="output_path",
        help="Destination for collated CSV."
    )
    args = parser.parse_args()

    try:
        collate_data(
            args.aohs_path,
            args.output_path,
        )
    except FileNotFoundError:
        sys.exit("Failed to find data")

if __name__ == "__main__":
    main()
