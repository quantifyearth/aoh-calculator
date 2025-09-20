import argparse
import os
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import pygbif # type: ignore
import requests
from pygbif.occurrences.download import GbifDownload # type: ignore

GBIF_USERNAME = os.environ['GBIF_USERNAME']
GBIF_EMAIL = os.environ['GBIF_EMAIL']
GBIF_PASSWORD = os.environ['GBIF_PASSWORD']

def generate_iucn_to_gbif_map(
    collated_data_path: Path,
    output_dir_path: Path,
) -> pd.DataFrame:
    collated_data = pd.read_csv(collated_data_path)

    # To save spamming the GBIF API, see if there's already a map
    # and if so we just request GBIF IDs for data we've not seen before
    map_filename = output_dir_path / "map.csv"
    id_map : Dict[int,Tuple[str,str,int,Optional[int]]] = {}
    try:
        existing_map = pd.read_csv(map_filename)
        for _, row in existing_map.iterrows():
            id_map[row.iucn_taxon_id] = (row.iucn_taxon_id, row.scientific_name, row.assessment_year, row.gbif_id)
    except (AttributeError, FileNotFoundError):
        pass

    # First we make a map
    for _, row in collated_data.iterrows():
        taxon_id = row.id_no
        if taxon_id in id_map:
            continue
        assessment_year = row.assessment_year
        scientific_name = row.scientific_name

        if not assessment_year:
            continue
        if not scientific_name:
            continue

        try:
            result = pygbif.species.name_backbone(scientific_name, rank='species')
            if result["matchType"] not in ["EXACT", "FUZZY"]:
                raise ValueError("no match found")
            gbif_id = result["usageKey"]

            id_map[taxon_id] = (taxon_id, scientific_name, assessment_year, int(gbif_id))
        except (KeyError, ValueError):
            id_map[taxon_id] = (taxon_id, scientific_name, assessment_year, None)
        except requests.exceptions.ConnectionError:
            # GBIF is not longer happy to talk to us? We should cache whatever data we already
            # have and give up
            map_data = id_map.values()
            map_df = pd.DataFrame(
                map_data,
                columns=["iucn_taxon_id", "scientific_name", "assessment_year", "gbif_id"],
            )
            map_df["gbif_id"] = map_df["gbif_id"].astype('Int64')
            map_df.to_csv(map_filename, index=False)
            sys.exit("Connection error from GBIF, aborting.")

        time.sleep(0.1) # rate limiting

    map_data = id_map.values()
    map_df = pd.DataFrame(
        map_data,
        columns=["iucn_taxon_id", "scientific_name", "assessment_year", "gbif_id"],
    )
    map_df["gbif_id"] = map_df["gbif_id"].astype('Int64')
    map_df.to_csv(map_filename, index=False)

    return map_df

def build_gbif_query(id_map: pd.DataFrame) -> Any:

    map_with_gbif_id = id_map[id_map.gbif_id is not None]

    queries = [
        {
            "type": "and",
            "predicates": [
                {
                    "type": "equals",
                    "key": "TAXON_KEY",
                    "value": int(gbif_id),
                },
                {
                    "type": "greaterThan",
                    "key": "YEAR",
                    "value": int(assessment_year),
                },
                {
                    "type": "equals",
                    "key": "HAS_COORDINATE",
                    "value": "TRUE"
                },
                {
                    "type": "equals",
                    "key": "HAS_GEOSPATIAL_ISSUE",
                    "value": "FALSE"
                }
            ]
        }
        for _, _, assessment_year, gbif_id in map_with_gbif_id.itertuples(index=False)
    ]

    return {
        "type": "or",
        "predicates": queries
    }

def build_point_validation_table(
    gbif_data_path: Path,
    map_df: pd.DataFrame,
    output_csv_path: Path,
) -> None:
    gbif_data = pd.read_csv(gbif_data_path, sep='\t')
    gbif_data.rename(columns={"taxonKey": "gbif_id"}, inplace=True)
    updated_data = gbif_data.merge(map_df, on="gbif_id", how='inner')
    necessary_columns = updated_data[["iucn_taxon_id", "gbif_id", "decimalLatitude", "decimalLongitude", "year"]]
    necessary_columns.to_csv(output_csv_path, index=False)

def fetch_gbif_data(
    collated_data_path: Path,
    output_dir_path: Path,
) -> None:
    final_result_path = output_dir_path / "points.csv"
    if final_result_path.exists():
        return

    os.makedirs(output_dir_path, exist_ok=True)
    download_key_cache_filename = output_dir_path / "download_key"

    map_df = generate_iucn_to_gbif_map(collated_data_path, output_dir_path)
    if map_df is None or len(map_df) == 0:
        sys.exit("No specices in GBIF ID list, aborting")

    if not download_key_cache_filename.exists():
        request = GbifDownload(GBIF_USERNAME, GBIF_EMAIL)
        query = build_gbif_query(map_df)
        request.add_predicate_dict(query)

        download_key = request.post_download(GBIF_USERNAME, GBIF_PASSWORD)
        download_key_cache_filename = output_dir_path / "download_key"
        with open(download_key_cache_filename, "w", encoding="UTF-8") as f:
            f.write(download_key)
    else:
        with open(download_key_cache_filename, "r", encoding="UTF-8") as f:
            download_key = f.read()

    expected_csv = output_dir_path / f"{download_key}.csv"
    if not expected_csv.exists():
        expected_download = output_dir_path / f"{download_key}.zip"
        if not expected_download.exists():
            while True:
                metadata = pygbif.occurrences.download_meta(download_key)
                match metadata["status"]:
                    case "PREPARING" | "SUSPENDED" | "RUNNING":
                        print(f"Download status: {metadata['status']}, sleeping...")
                        time.sleep(30.0)
                        continue
                    case "SUCCEEDED":
                        file_path = pygbif.occurrences.download_get(download_key, path=output_dir_path)
                        print(f"Results are in {file_path}")
                        break
                    case _:
                        sys.exit(f"Failed to download data, status: {metadata['status']}")
        with zipfile.ZipFile(expected_download, 'r') as zip_file:
            zip_file.extractall(output_dir_path)
        if not expected_csv.exists():
            sys.exit("Extracted GBIF zip did not contain expected CSV file")

    build_point_validation_table(
        expected_csv,
        map_df,
        final_result_path,
    )

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch GBIF records for species for validation.")
    parser.add_argument(
        '--collated_aoh_data',
        type=Path,
        help="CSV containing collated AoH data",
        required=True,
        dest="collated_data_path"
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        required=True,
        dest="output_dir_path",
        help="Destination directory for GBIF data."
    )
    args = parser.parse_args()

    fetch_gbif_data(
        args.collated_data_path,
        args.output_dir_path,
    )


if __name__ == "__main__":
    main()
