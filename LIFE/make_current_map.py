import argparse 
import itertools
from typing import Dict, Optional
from multiprocessing import Pool, cpu_count, set_start_method

import numpy as np
import pandas as pd
from alive_progress import alive_bar
from yirgacheffe.layers import RasterLayer

# From Eyres et al: The current layer maps IUCN level 1 and 2 habitats, but habitats in the PNV layer are mapped only at IUCN level 1, 
# so to estimate species’ proportion of original AOH now remaining we could only use natural habitats mapped at level 1 and artificial 
# habitats at level 2.
IUCN_CODE_ARTIFICAL = [
    "14", "14.1", "14.2", "14.3", "14.4", "14.5", "14.6"
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


def make_current_map(
    current_path: str,
    crosswalk_path: str,
    output_path: str,
    concurrency: Optional[int],
    show_progress: bool,
) -> None:
    with RasterLayer.layer_from_file(current_path) as current:
        crosswalk = load_crosswalk_table(crosswalk_path)

        map_preserve_code = list(itertools.chain.from_iterable([crosswalk[x] for x in IUCN_CODE_ARTIFICAL]))

        def filter(a):
            import numpy as np
            return np.where(np.isin(a, map_preserve_code), a, (np.floor(a / 100) * 100).astype(int))

        calc = current.numpy_apply(filter)

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
    set_start_method("spawn")

    parser = argparse.ArgumentParser(description="Zenodo resource downloader.")
    parser.add_argument(
        '--jung_l2',
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

    make_current_map(
        args.current_path,
        args.crosswalk_path,
        args.results_path,
        args.concurrency,
        args.show_progress,
    )

if __name__ == "__main__":
    main()
