import argparse 
import itertools
from typing import Dict

import numpy as np
import pandas as pd
from yirgacheffer.layers import RasterLayer

# From Eyres et al: The current layer maps IUCN level 1 and 2 habitats, but habitats in the PNV layer are mapped only at IUCN level 1, 
# so to estimate species’ proportion of original AOH now remaining we could only use natural habitats mapped at level 1 and artificial 
# habitats at level 2.
IUCN_CODE_PRESERVE = [
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


def make_restore_map(
    current_path: str,
    crosswalk_path: str,
    output_path: str
) -> None:
    current = RasterLayer.layer_from_file(current_path)
    crosswalk = load_crosswalk_table(crosswalk_path)

    map_preserve_code = list(itertools.chain.from_iterable([crosswalk[x] for x in IUCN_CODE_PRESERVE]))

    calc = current.numpy_apply(
        lambda a: np.where(np.isin(a, map_preserve_code), a, (np.floor(a / 100) * 100).astype(int))
    )
    
    result = RasterLayer.empty_raster_layer_like(
        current,
        filename=output_path
    )
    calc.save(result)


def main() -> None:
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
    args = parser.parse_args()

    make_restore_map(
        args.pnv_path,
        args.current_path,
        args.crosswalk_path,
        args.results_path,
    )

if __name__ == "__main__":
    main()
