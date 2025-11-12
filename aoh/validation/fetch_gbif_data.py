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

def generate_iucn_to_gbif_map(
    collated_data_path: Path,
    output_dir_path: Path,
    taxa: str,
) -> pd.DataFrame:
    collated_data = pd.read_csv(collated_data_path)

    # To save spamming the GBIF API, see if there's already a map
    # and if so we just request GBIF IDs for data we've not seen before
    map_filename = output_dir_path / "map.csv"
    id_map : Dict[int,Tuple[str,str,int,Optional[int],str]] = {}
    try:
        existing_map = pd.read_csv(map_filename)
        for _, row in existing_map.iterrows():
            id_map[row.iucn_taxon_id] = (
                row.iucn_taxon_id,
                row.scientific_name,
                row.assessment_year,
                row.gbif_id,
                row.class_name
            )
    except (AttributeError, FileNotFoundError):
        pass

    # First we make a map
    for _, row in collated_data[collated_data.class_name==taxa].iterrows():
        taxon_id = row.id_no
        if taxon_id in id_map:
            print(f"skipping {taxon_id}")
            continue
        assessment_year = row.assessment_year
        scientific_name = row.scientific_name
        class_name = row.class_name

        if not assessment_year:
            continue
        if not scientific_name:
            continue

        try:
            result = pygbif.species.name_backbone(scientific_name, rank='species')
            if result["matchType"] not in ["EXACT", "FUZZY"]:
                raise ValueError("no match found")
            gbif_id = result["speciesKey"]

            id_map[taxon_id] = (taxon_id, scientific_name, assessment_year, int(gbif_id), class_name)
        except (KeyError, ValueError):
            id_map[taxon_id] = (taxon_id, scientific_name, assessment_year, None, class_name)
        except requests.exceptions.ConnectionError as exc:
            # GBIF is not longer happy to talk to us? We should cache whatever data we already
            # have and give up
            map_data = id_map.values()
            map_df = pd.DataFrame(
                map_data,
                columns=["iucn_taxon_id", "scientific_name", "assessment_year", "gbif_id", "class_name"],
            )
            map_df["gbif_id"] = map_df["gbif_id"].astype('Int64')
            map_df.to_csv(map_filename, index=False)
            print(exc)
            sys.exit("Connection error from GBIF, aborting.")

        time.sleep(0.5) # rate limiting

    map_data = id_map.values()
    map_df = pd.DataFrame(
        map_data,
        columns=["iucn_taxon_id", "scientific_name", "assessment_year", "gbif_id", "class_name"],
    )
    map_df["gbif_id"] = map_df["gbif_id"].astype('Int64')
    map_df.to_csv(map_filename, index=False)

    return map_df

def build_gbif_query(id_map: pd.DataFrame) -> Any:

    map_with_gbif_id = id_map[id_map.gbif_id.notna()]
    request_data = map_with_gbif_id[["assessment_year", "gbif_id"]]

    # There should be tens of assessment years vs thousands of species, so we can use that to reduce the query count:
    grouped = request_data.groupby('assessment_year')['gbif_id'].apply(list)

    queries = [
        {
            "type": "and",
            "predicates": [
                {
                    "type": "in",
                    "key": "TAXON_KEY",
                    "values": [str(int(gbif_id)) for gbif_id in gbif_ids]
                },
                {
                    "type": "greaterThan",
                    "key": "YEAR",
                    "value": str(int(assessment_year)), # type: ignore
                },
            ]
        }
        for assessment_year, gbif_ids in grouped.items()
    ]

    return {
        "type": "and",
        "predicates": [
            {
                "type": "or",
                "predicates": queries
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
            },
        ]
    }

def build_point_validation_table(
    gbif_data_path: Path,
    map_df: pd.DataFrame,
    output_csv_path: Path,
) -> None:
    gbif_data = pd.read_csv(gbif_data_path, sep='\t')
    gbif_data.rename(columns={"speciesKey": "gbif_id"}, inplace=True)
    updated_data = gbif_data.merge(map_df, on="gbif_id", how='inner')
    necessary_columns = updated_data[["iucn_taxon_id", "gbif_id", "decimalLatitude", "decimalLongitude", "year"]]
    necessary_columns.to_csv(output_csv_path, index=False)

def fetch_gbif_data(
    collated_data_path: Path,
    taxa: str,
    gbif_username: str,
    gbif_email: str,
    gbif_password: str,
    toplevel_output_dir_path: Path,
) -> None:
    taxa_output_dir_path = toplevel_output_dir_path / taxa
    final_result_path = taxa_output_dir_path / "points.csv"
    if final_result_path.exists():
        return

    os.makedirs(taxa_output_dir_path, exist_ok=True)
    download_key_cache_filename = taxa_output_dir_path / "download_key"

    map_df = generate_iucn_to_gbif_map(collated_data_path, taxa_output_dir_path, taxa)
    if map_df is None or len(map_df) == 0:
        sys.exit("No specices in GBIF ID list, aborting")

    if not download_key_cache_filename.exists():
        request = GbifDownload(gbif_username, gbif_email)
        query = build_gbif_query(map_df)
        request.add_predicate_dict(query)

        download_key = request.post_download(gbif_username, gbif_password)
        download_key_cache_filename = taxa_output_dir_path / "download_key"
        with open(download_key_cache_filename, "w", encoding="UTF-8") as f:
            f.write(download_key)
    else:
        with open(download_key_cache_filename, "r", encoding="UTF-8") as f:
            download_key = f.read()

    expected_csv = taxa_output_dir_path / f"{download_key}.csv"
    if not expected_csv.exists():
        expected_download = taxa_output_dir_path / f"{download_key}.zip"
        if not expected_download.exists():
            while True:
                metadata = pygbif.occurrences.download_meta(download_key)
                match metadata["status"]:
                    case "PREPARING" | "SUSPENDED" | "RUNNING":
                        print(f"Download status: {metadata['status']}, sleeping...")
                        time.sleep(30.0)
                        continue
                    case "SUCCEEDED":
                        file_path = pygbif.occurrences.download_get(download_key, path=taxa_output_dir_path)
                        print(f"Results are in {file_path}")
                        break
                    case _:
                        sys.exit(f"Failed to download data, status: {metadata['status']}")
        with zipfile.ZipFile(expected_download, 'r') as zip_file:
            zip_file.extractall(taxa_output_dir_path)
        if not expected_csv.exists():
            sys.exit("Extracted GBIF zip did not contain expected CSV file")

    build_point_validation_table(
        expected_csv,
        map_df,
        final_result_path,
    )

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch GBIF records for species for validation.",
        epilog='''
Environment Variables:
    GBIF_USERNAME   Username of user's GBIF account.
    GBIF_EMAIL      E-mail of user's GBIF account.
    GBIF_PASSWORD   Password of user's GBIF account.
            ''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--collated_aoh_data',
        type=Path,
        help="CSV containing collated AoH data",
        required=True,
        dest="collated_data_path",
    )
    parser.add_argument(
        '--gbif_username',
        type=str,
        default=os.getenv('GBIF_USERNAME'),
        help="Username of user's GBIF account. Can also be set in environment.",
        dest="gbif_username",
    )
    parser.add_argument(
        '--gbif_email',
        type=str,
        default=os.getenv('GBIF_EMAIL'),
        help="E-mail of user's GBIF account. Can also be set in environment.",
        dest="gbif_email",
    )
    parser.add_argument(
        '--gbif_password',
        type=str,
        default=os.getenv('GBIF_PASSWORD'),
        help="Password of user's GBIF account. Can also be set in environment.",
        dest="gbif_password",
    )
    parser.add_argument(
        '--taxa',
        type=str,
        required=True,
        dest='taxa',
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        required=True,
        dest="output_dir_path",
        help="Destination directory for GBIF data.",
    )
    args = parser.parse_args()

    if not args.gbif_username:
        parser.error('--gbif_username is required (or set GBIF_USERNAME env var)')
    if not args.gbif_email:
        parser.error('--gbif_email is required (or set GBIF_EMAIL env var)')
    if not args.gbif_password:
        parser.error('--gbif_password is required (or set GBIF_PASSWORD env var)')

    fetch_gbif_data(
        args.collated_data_path,
        args.taxa,
        args.gbif_username,
        args.gbif_email,
        args.gbif_password,
        args.output_dir_path,
    )


if __name__ == "__main__":
    main()
