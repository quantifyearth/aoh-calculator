import argparse
import os
import logging
from functools import partial
from importlib.metadata import version
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Optional, Set

import numpy as np
import psutil
import yirgacheffe as yg
from osgeo import gdal   # type: ignore

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')

BLOCKSIZE = 512

def _enumerate_subset(
    habitat_path: Path,
    offset: int,
) -> Set[int]:
    gdal.SetCacheMax(1 * 1024 * 1024 * 1024)
    with yg.read_raster(habitat_path) as habitat_map:
        width, height = habitat_map.dimensions
        blocksize = min(BLOCKSIZE, height - offset)
        data = habitat_map.read_array(0, offset, width, blocksize)
        values = np.unique(data)
        without_nans = values[~np.isnan(values)]
        res = {int(x) for x in without_nans}
    return res

def enumerate_terrain_types(
    habitat_path: Path
) -> Set[int]:
    gdal.SetCacheMax(1 * 1024 * 1024 * 1024)
    with yg.read_raster(habitat_path) as habitat_map:
        _, ysize = habitat_map.dimensions
    blocks = range(0, ysize, BLOCKSIZE)
    logger.info("Enumerating habitat classes in raster...")
    with Pool(processes=int(cpu_count() / 2)) as pool:
        sets = pool.map(partial(_enumerate_subset, habitat_path), blocks)
    superset = set()
    for s in sets:
        superset.update(s)
    try:
        superset.remove(0)
    except KeyError:
        pass
    return superset

class VsimemFile:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self.path

    def __exit__(self, *args):
        try:
            gdal.Unlink(self.path)
        except RuntimeError:
            pass

def make_single_type_map(
    habitat_path: Path,
    pixel_scale: Optional[float],
    target_projection: Optional[str],
    output_directory_path: Path,
    max_threads: int,
    habitat_value: int | float,
) -> None:
    logger.info("Building layer for %s...", habitat_value)

    mem_stats = psutil.virtual_memory()
    available_mem = mem_stats.available
    gdal.SetCacheMax(available_mem)
    gdal.SetConfigOption('GDAL_NUM_THREADS', str(max_threads))

    with yg.read_raster(habitat_path) as habitat_map:
        logger.info("Filtering for %s...", habitat_value)
        filtered_map = habitat_map == habitat_value

        if pixel_scale is not None and target_projection is not None:
            filtered_map = filtered_map.as_type(yg.DataType.Float32).as_projection(
                yg.MapProjection(target_projection, pixel_scale, -pixel_scale),
                yg.ResamplingMethod.Average
            )

        filename = f"lcc_{habitat_value}.tif"
        filtered_map.to_geotiff(output_directory_path / filename, parallelism=True)


def habitat_process(
    habitat_path: Path,
    pixel_scale: Optional[float],
    target_projection: Optional[str],
    output_directory_path: Path,
    process_count: int
) -> None:
    os.makedirs(output_directory_path, exist_ok=True)

    # We need to know how many terrains there are. We could get this from the crosswalk
    # table, but we can also work out the unique values ourselves. In practice this is
    # worth the effort, otherwise we generate a lot of empty maps potentially.
    habitats = enumerate_terrain_types(habitat_path)

    for habitat in habitats:
        make_single_type_map(
            habitat_path,
            pixel_scale,
            target_projection,
            output_directory_path,
            process_count,
            habitat,
        )

def main() -> None:
    parser = argparse.ArgumentParser(description="Downsample habitat map to raster per terrain type.")
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {version("aoh")}'
    )
    parser.add_argument(
        '--habitat',
        type=Path,
        help="Path of initial combined habitat map.",
        required=True,
        dest="habitat_path"
    )
    parser.add_argument(
        "--scale",
        type=float,
        required=False,
        dest="pixel_scale",
        help="Optional output pixel scale value, otherwise same as source."
    )
    parser.add_argument(
        '--projection',
        type=str,
        help="Optional target projection, otherwise same as source.",
        required=False,
        dest="target_projection",
        default=None
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        dest="output_path",
        help="Destination folder for raster files."
    )
    parser.add_argument(
        "-j",
        type=int,
        required=False,
        default=cpu_count(),
        dest="processes_count",
        help="Optional number of concurrent threads to use."
    )
    args = parser.parse_args()

    has_projection = args.target_projection is not None
    has_scale = args.pixel_scale is not None
    if has_projection ^ has_scale:
        parser.error("Specify either both --projection and --scale must be specified or neither")

    habitat_process(
        args.habitat_path,
        args.pixel_scale,
        args.target_projection,
        args.output_path,
        args.processes_count,
    )

if __name__ == "__main__":
    main()
