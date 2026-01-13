import argparse
import json
import logging
import math
import os
import sys
from pathlib import Path

import pandas as pd
import yirgacheffe as yg
from geopandas import gpd # type: ignore
from alive_progress import alive_bar # type: ignore

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')

def main() -> None:
    parser = argparse.ArgumentParser(description="Area of habitat calculator.")
    parser.add_argument(
        '--habitats',
        type=Path,
        help="Directory of habitat rasters, one per habitat class.",
        required=True,
        dest="habitat_path"
    )
    parser.add_argument(
        '--elevation-min',
        type=Path,
        help="Minimum elevation raster.",
        required=True,
        dest="min_elevation_path",
    )
    parser.add_argument(
        '--elevation-max',
        type=Path,
        help="Maximum elevation raster",
        required=True,
        dest="max_elevation_path",
    )
    parser.add_argument(
        '--area',
        type=Path,
        help="Optional area per pixel raster. Can be 1xheight.",
        required=False,
        dest="area_path",
    )
    parser.add_argument(
        '--crosswalk',
        type=str,
        help="Path of habitat crosswalk table.",
        required=True,
        dest="crosswalk_path",
    )
    parser.add_argument(
        '--speciesdata',
        type=Path,
        help="Single species/seasonality geojson.",
        required=True,
        dest="species_data_path"
    )
    parser.add_argument(
        '--force-habitat',
        help="If set, don't treat an empty habitat layer layer as per IRTWG.",
        dest="force_habitat",
        action='store_true',
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Directory where area geotiffs should be stored.',
        required=True,
        dest='output_path',
    )
    args = parser.parse_args()

    aohcalc(
        args.habitat_path,
        args.min_elevation_path,
        args.max_elevation_path,
        args.area_path,
        args.crosswalk_path,
        args.species_data_path,
        args.force_habitat,
        args.output_path
    )

if __name__ == "__main__":
    main()
