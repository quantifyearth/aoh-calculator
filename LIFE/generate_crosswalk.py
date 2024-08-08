import argparse
import os

import pandas as pd
from iucn_modlib.translator import toJung


# Take from https://www.iucnredlist.org/resources/habitat-classification-scheme
IUCN_HABITAT_CODES = [
    "1", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9",
    "2", "2.1", "2.2",
    "3", "3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "3.8",
    "4", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7",
    "5", "5.1", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "5.8", "5.9",
    "5.10", "5.11", "5.12", "5.13", "5.14", "5.15", "5.16", "5.17", "5.18",
    "6"
    "7", "7.1", "7.2",
    "8", "8.1", "8.2", "8.3",
    "9", "9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8", "9.9", "9.10",
    "9.8.1", "9.8.2", "9.8.3", "9.8.4", "9.8.5", "9.8.6",
    "10", "10.1", "10.2", "10.3", "10.4",
    "11", "11.1", "11.1.1", "11.1.2", "11.2", "11.3", "11.4", "11.5", "11.6",
    "12", "12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.7",
    "13", "13.1", "13.2", "13.3", "13.4", "13.5",
    "14", "14.1", "14.2", "14.3", "14.4", "14.5", "14.6",
    "15", "15.1", "15.2", "15.3", "15.4", "15.5", "15.6", "15.7", "15.8",
    "15.9", "15.10", "15.11", "15.12", "15.13",
    "16",
    "17",
    "18",
]

def generate_crosswalk(
    output_filename: str,
) -> None:
    output_dir, _ = os.path.split(output_filename)
    os.makedirs(output_dir, exist_ok=True)

    res = []
    for iucn_code in IUCN_HABITAT_CODES:
        try:
            for jung_code in toJung([iucn_code]):
                res.append([iucn_code, jung_code])
        except ValueError:
            continue

    df = pd.DataFrame(res, columns=["code", "value"])
    df.to_csv(output_filename, index=False)

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Jung crosswalk table as CSV.")
    parser.add_argument(
        '--output',
        type=str,
        help='Path where final crosswalk should be stored',
        required=True,
        dest='output_filename',
    )
    args = parser.parse_args()
    generate_crosswalk(args.output_filename)

if __name__ == "__main__":
    main()
