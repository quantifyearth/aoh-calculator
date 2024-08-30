import argparse 
import itertools
import os
import shutil
import tempfile
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from alive_progress import alive_bar
from yirgacheffe.layers import RasterLayer

# From Eyres et al: In the conversion scenario all habitats currently mapped as natural or pasture were converted to arable land
IUCN_CODE_ARTIFICAL = [
    "14", "14.3", "14.4", "14.5", "14.6"
]
ARABLE = "14.1"

def load_crosswalk_table(table_file_name: str) -> Dict[str,int]:
    rawdata = pd.read_csv(table_file_name)
    result = {}
    for _, row in rawdata.iterrows():
        try:
            result[row.code].append(int(row.value))
        except KeyError:
            result[row.code] = [int(row.value)]
    return result


def make_arable_map(
    current_path: str,
    crosswalk_path: str,
    output_path: str,
    concurrency: Optional[int],
    show_progress: bool,
) -> None:
    with RasterLayer.layer_from_file(current_path) as current:
        crosswalk = load_crosswalk_table(crosswalk_path)

        map_preserve_code = list(itertools.chain.from_iterable([crosswalk[x] for x in IUCN_CODE_ARTIFICAL]))
        # arable_code = crosswalk[ARABLE][0]
        arable_code = 1401 # This is a hack as Daniele's crosswalk has 14.1 mapped to both 1400 and 1401 and there's no logical way
        # to understand this

        calc = current.numpy_apply(
            lambda a: np.where(np.isin(a, map_preserve_code), a, arable_code)
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
    parser = argparse.ArgumentParser(description="Generate the arable scenario map.")
    parser.add_argument(
        '--current',
        type=str,
        help='Path of Jung L2 map',
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

    make_arable_map(
        args.current_path,
        args.crosswalk_path,
        args.results_path,
        args.concurrency,
        args.show_progress,
    )

if __name__ == "__main__":
    main()
