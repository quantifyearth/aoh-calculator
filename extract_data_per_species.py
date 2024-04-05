import argparse
import os

import geopandas as gpd
# import pyshark # pylint: disable=W0611

def extract_data_per_species(
    speciesdata_path: str,
    output_directory_path: str,
) -> None:
    os.makedirs(output_directory_path, exist_ok=True)

    species_data = gpd.read_file(speciesdata_path)
    subset_of_interest = species_data[[
        "id_no",
        "seasonal",
        "elevation_lower",
        "elevation_upper",
        "full_habitat_code",
        "geometry"
    ]]
    for _, row in subset_of_interest.iterrows():
        output_path = os.path.join(output_directory_path, f"{row.id_no}_{row.seasonal}.geojson")
        res = gpd.GeoDataFrame(row.to_frame().transpose(), crs=species_data.crs, geometry="geometry")
        res.to_file(output_path, driver="GeoJSON")

def main() -> None:
    parser = argparse.ArgumentParser(description="Process agregate species data to per-species-file.")
    parser.add_argument(
        '--speciesdata',
        type=str,
        help="Combined species metadata",
        required=True,
        dest="speciesdata_path",
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Directory where per species Geojson is stored',
        required=True,
        dest='output_directory_path',
    )
    args = parser.parse_args()

    extract_data_per_species(
        args.speciesdata_path,
        args.output_directory_path
    )

if __name__ == "__main__":
    main()
