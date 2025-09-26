import argparse
import os
from pathlib import Path

def validate_occurences(
    gbif_data_path: Path,
    aohs_path: Path,
    output_path: Path,
) -> None:
    os.makedirs(output_path.parent, exist_ok=True)

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate map prevalence.")
    parser.add_argument(
        '--gbif_data_path',
        type=Path,
        help="Data containing downloaded GBIF data.",
        required=True,
        dest="gbif_data_path"
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
        help="CSV of outliers."
    )
    args = parser.parse_args()

    validate_occurences(
        args.gbif_data_path,
        args.aohs_path,
        args.output_path,
    )

if __name__ == "__main__":
    main()
