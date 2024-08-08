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


# def make_arable_mapset(
#     current_mapset_path: str,
#     crosswalk_path: str,
#     output_path: str,
#     show_progress: bool,
# ) -> None:
#     os.makedirs(output_path, exist_ok=True)

#     crosswalk = load_crosswalk_table(crosswalk_path)
#     artificial_codes: List[int] = list(itertools.chain.from_iterable([crosswalk[x] for x in IUCN_CODE_ARTIFICAL]))
#     arable_code = crosswalk[ARABLE][0]

#     habitat_layers = os.listdir(current_mapset_path)
#     covertsion_layers = []
#     arable_layer = None
#     for layername in habitat_layers:
#         full_habitat_path = os.path.join(current_mapset_path, layername)
#         layercode, _ = os.path.splitext(layername)
#         layercode = int(layercode)

#         if layercode == arable_code:
#             assert arable_layer is None
#             arable_layer = full_habitat_path
#         elif layercode not in artificial_codes:
#             covertsion_layers.append(full_habitat_path)
#         else:
#             target_path = os.path.join(output_path, layername)
#             shutil.copy(full_habitat_path, target_path)

#     assert arable_layer is not None

#     # finally build up the arable layer
#     with tempfile.TemporaryDirectory() as tmpdir:
#         new_arable_layey_path = os.path.join(tmpdir, f"{arable_code}.tif")
#         current_arable = RasterLayer.layer_from_file(arable_layer)
#         target_layer = RasterLayer.empty_layer_like_file(current_arable, filename=new_arable_layey_path)
#         calc = current_arable
#         for layer_path in covertsion_layers:
#             raster = RasterLayer.layer_fromfile(layer_path)
#             # We could naively assume that the two layers have no overlap if it wasn't
#             # for the fact we rescaled the data, so we can't just add the layers
#             calc = calc.numpy_apply(
#                 lambda a, b: np.where(b > 0, 1, a),
#                 raster
#             )
#         calc.save(target_layer)
#         target_layer.close()

#         shutil.copy(new_arable_layey_path, os.path.join(output_path, f"{arable_code}.tif"))


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
