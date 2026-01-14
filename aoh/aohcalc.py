import argparse
import logging
from pathlib import Path

from . import aohcalc_fractional, aohcalc_binary

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')

def main() -> None:
    parser = argparse.ArgumentParser(description="Area of habitat calculator.")

    # land cover/habitat map arguments - either single raster for binary or directory for many
    parser.add_argument(
        '--fractional_habitats',
        type=Path,
        help="Directory of fractional habitat rasters, one per habitat class.",
        required=False,
        dest="fractional_habitat_path",
    )
    parser.add_argument(
        '--classified_habitat',
        type=Path,
        help="Habitat raster, with each class a discrete value per pixel.",
        required=False,
        dest="discrete_habitat_path",
    )

    # Elevation arguments - either single or min/max pair
    parser.add_argument(
        '--elevation',
        type=Path,
        help="Elevation raster (for high-resolution analyses).",
        required=False,
        dest="elevation_path",
    )
    parser.add_argument(
        '--elevation-min',
        type=Path,
        help="Minimum elevation raster (for downscaled analyses).",
        required=False,
        dest="min_elevation_path",
    )
    parser.add_argument(
        '--elevation-max',
        type=Path,
        help="Maximum elevation raster (for downscaled analyses).",
        required=False,
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

    has_fractional = args.fractional_habitat_path is not None
    has_discrete = args.discrete_habitat_path is not None
    if has_fractional and has_discrete:
        parser.error("Specify either --fractional_habitats or --classified_habitat, not both")
    elif not has_fractional and not has_discrete:
        parser.error("Must specify either --fractional_habitats or --classified_habitat")

    has_single = args.elevation_path is not None
    has_minmax = (args.min_elevation_path is not None) or (args.max_elevation_path is not None)

    if has_single and has_minmax:
        parser.error("Specify either --elevation or --elevation-min/--elevation-max, not both")
    elif not has_single and not has_minmax:
        parser.error("Must specify either --elevation or both --elevation-min and --elevation-max")
    elif has_minmax and (args.min_elevation_path is None or args.max_elevation_path is None):
        parser.error("Both --elevation-min and --elevation-max must be specified together")

    if has_single:
        elevation = args.elevation_path
    else:
        elevation = (args.min_elevation_path, args.max_elevation_path)

    if has_fractional:
        aohcalc_fractional(
            args.fractional_habitat_path,
            elevation,
            args.crosswalk_path,
            args.species_data_path,
            args.output_path,
            [args.area_path] if args.area_path else [],
            args.force_habitat,
        )
    else:
        aohcalc_binary(
            args.discrete_habitat_path,
            elevation,
            args.crosswalk_path,
            args.species_data_path,
            args.output_path,
            [args.area_path] if args.area_path else [],
            args.force_habitat,
        )

if __name__ == "__main__":
    main()
