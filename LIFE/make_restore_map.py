import argparse 
import itertools
from typing import Dict

import numpy as np
import pandas as pd
from yirgacheffer.layers import RasterLayer

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
    output_path: str
) -> None:
    pnv = RasterLayer.layer_from_file(pnv_path)
    current = RasterLayer.layer_from_file(current_path)
    crosswalk = load_crosswalk_table(crosswalk_path)

    map_replacement_codes = list(itertools.chain.from_iterable([crosswalk[x] for x in IUCN_CODE_REPLACEMENTS]))

    intersection = RasterLayer.find_intersection([pnv, current])
    for layer in [pnv, current]:
        layer.set_window_for_intersection(intersection)

    calc = current.numpy_apply(
        lambda a, b: np.where(np.isin(a, map_replacement_codes), b, a),
        pnv
    )
    
    result = RasterLayer.empty_raster_layer_like(
        current,
        filename=output_path
    )
    calc.save(result)


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
    args = parser.parse_args()

    make_restore_map(
        args.pnv_path,
        args.current_path,
        args.crosswalk_path,
        args.results_path,
    )

if __name__ == "__main__":
    main()
