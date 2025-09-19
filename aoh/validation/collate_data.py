import argparse
import json
import os
import sys
from glob import glob

import pandas as pd

COLUMNS = [
    "id_no",
    "assessment_id",
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
    aoh_results: str,
    output_path: str,
) -> None:
    manifests = [os.path.join(aoh_results, fn) for fn in glob("**/*.json", root_dir=aoh_results, recursive=True)]
    if not manifests:
        print(f"Found no manifests in {aoh_results}", file=sys.stderr)
        sys.exit(-1)

    output_dir, _ = os.path.split(output_path)
    os.makedirs(output_dir, exist_ok=True)

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
    parser = argparse.ArgumentParser(description="Collate metadata from AoH build.")
    parser.add_argument(
        '--aoh_results',
        type=str,
        help="Path of all the AoH outputs.",
        required=True,
        dest="aohs_path"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        dest="output_path",
        help="Destination for collated CSV."
    )
    args = parser.parse_args()

    collate_data(
        args.aohs_path,
        args.output_path,
    )

if __name__ == "__main__":
    main()
