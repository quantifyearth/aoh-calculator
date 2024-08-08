import argparse 
import itertools
import sys
from typing import Dict, Optional

import numpy as np
import pandas as pd
from alive_progress import alive_bar
from yirgacheffe.layers import RasterLayer, RescaledRasterLayer

# From Eyres et al: In the restoration scenario all areas classified as arable or pasture were restored to their PNV
IUCN_CODE_REPLACEMENTS = [
    "14.1",
    "14.2"
]

def load_crosswalk_table(table_file_name: str) -> Dict[str,int]:
    rawdata = pd.read_csv(table_file_name)
    result = {}
    for _, row in rawdata.iterrows():
        try:
            result[row.code].append(int(row.value))
        except KeyError:
            result[row.code] = [int(row.value)]
    return result


def make_restore_map(
    pnv_path: str,
    current_path: str,
    crosswalk_path: str,
    output_path: str,
    concurrency: Optional[int],
    show_progress: bool,
) -> None:
    with RasterLayer.layer_from_file(current_path) as current:
        with RescaledRasterLayer.layer_from_file(pnv_path, current.pixel_scale) as pnv:
            crosswalk = load_crosswalk_table(crosswalk_path)

            map_replacement_codes = list(itertools.chain.from_iterable([crosswalk[x] for x in IUCN_CODE_REPLACEMENTS]))

            try:
                intersection = RasterLayer.find_intersection([pnv, current])
            except ValueError:
                print(f"Layers do not match in pixel scale or projection:\n", file=sys.stderr)
                print(f"\t{pnv_path}: {pnv.pixel_scale}, {pnv.projection}")
                print(f"\t{current_path}: {current.pixel_scale}, {current.projection}")
                sys.exit(-1)

            for layer in [pnv, current]:
                layer.set_window_for_intersection(intersection)

            calc = current.numpy_apply(
                lambda a, b: np.where(np.isin(a, map_replacement_codes), b, a),
                pnv
            )

            with RasterLayer.empty_raster_layer_like(
                current,
                filename=output_path,
                threads=16
            ) as result:
                if show_progress:
                    with alive_bar(manual=True) as bar:
                        calc.parallel_save(result, callback=bar, parallelism=concurrency)
                else:
                    calc.parallel_save(result, parallelism=concurrency)


def main() -> None:
    parser = argparse.ArgumentParser(description="Zenodo resource downloader.")
    parser.add_argument(
        '--pnv',
        type=str,
        help='Path of PNV map',
        required=True,
        dest='pnv_path',
    )
    parser.add_argument(
        '--currentl2',
        type=str,
        help='Path of current L2 map',
        required=True,
        dest='current_path',
    )
    parser.add_argument(
        '--crosswalk',
        type=str,
        help='Path of map to IUCN crosswalk table',
        required=True,
        dest='crosswalk_path',
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Path where final map should be stored',
        required=True,
        dest='results_path',
    )
    parser.add_argument(
        '-j',
        type=int,
        help='Number of concurrent threads to use for calculation.',
        required=False,
        default=None,
        dest='concurrency',
    )
    parser.add_argument(
        '-p',
        help="Show progress indicator",
        default=False,
        required=False,
        action='store_true',
        dest='show_progress',
    )
    args = parser.parse_args()

    make_restore_map(
        args.pnv_path,
        args.current_path,
        args.crosswalk_path,
        args.results_path,
        args.concurrency,
        args.show_progress,
    )

if __name__ == "__main__":
    main()
