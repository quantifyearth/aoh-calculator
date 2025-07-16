import argparse
import math
import os
import logging
import shutil
import tempfile
from functools import partial
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Optional, Set

import numpy as np
import psutil
from osgeo import gdal
from yirgacheffe.layers import RasterLayer  # type: ignore

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')

BLOCKSIZE = 512

def enumerate_subset(
    habitat_path: str,
    offset: int,
) -> Set[int]:
    gdal.SetCacheMax(1 * 1024 * 1024 * 1024)
    with RasterLayer.layer_from_file(habitat_path) as habitat_map:
        blocksize = min(BLOCKSIZE, habitat_map.window.ysize - offset)
        data = habitat_map.read_array(0, offset, habitat_map.window.xsize, blocksize)
        values = np.unique(data)
        without_nans = values[~np.isnan(values)]
        res = {int(x) for x in without_nans}
    return res

def enumerate_terrain_types(
    habitat_path: str
) -> Set[int]:
    gdal.SetCacheMax(1 * 1024 * 1024 * 1024)
    with RasterLayer.layer_from_file(habitat_path) as habitat_map:
        ysize = habitat_map.window.ysize
    blocks = range(0, ysize, BLOCKSIZE)
    logger.info("Enumerating habitat classes in raster...")
    with Pool(processes=int(cpu_count() / 2)) as pool:
        sets = pool.map(partial(enumerate_subset, habitat_path), blocks)
    superset = set()
    for s in sets:
        superset.update(s)
    return superset

def make_single_type_map(
    habitat_path: str,
    pixel_scale: Optional[float],
    target_projection: Optional[str],
    output_directory_path: str,
    habitat_value: int | float,
) -> None:
    logger.info("Building layer for %s...", habitat_value)

    # We could do this via yirgacheffe if it wasn't for the need to
    # both rescale and reproject. So we do the initial filtering
    # in that, but then bounce it to a temporary file for the
    # warping
    with tempfile.TemporaryDirectory() as tmpdir:
        with RasterLayer.layer_from_file(habitat_path) as habitat_map:
            logger.info("Filtering for %s...", habitat_value)
            calc = habitat_map == habitat_value
            with RasterLayer.empty_raster_layer_like(habitat_map, datatype=gdal.GDT_Byte) as filtered_map:
                calc.save(filtered_map)

                filename = f"lcc_{habitat_value}.tif"
                tempname = os.path.join(tmpdir, filename)

                dataset = filtered_map._dataset  # pylint: disable=W0212
                logger.info("Projecting %s...", habitat_value)
                gdal.Warp(tempname, dataset, options=gdal.WarpOptions(
                    creationOptions=['COMPRESS=LZW', 'NUM_THREADS=16'],
                    multithread=True,
                    dstSRS=target_projection,
                    outputType=gdal.GDT_Float32,
                    xRes=pixel_scale,
                    yRes=((0.0 - pixel_scale) if pixel_scale else pixel_scale),
                    resampleAlg="average",
                    workingType=gdal.GDT_Float32
                ))

        logger.info("Saving %s...", habitat_value)
        shutil.move(tempname, output_directory_path / filename)

def habitat_process(
    habitat_path: Path,
    pixel_scale: Optional[float],
    target_projection: Optional[str],
    output_directory_path: Path,
    process_count: int
) -> None:
    os.makedirs(output_directory_path, exist_ok=True)

    with RasterLayer.layer_from_file(habitat_path) as habitat_map:
        # The processing stage uses GDAL warp directly, with no chunking, so we should
        # take a guess at how much memory we need based on the dimensions of the base map
        pixels = habitat_map.window.xsize * habitat_map.window.ysize
        # I really tried not to write this statement and use introspection, but nothing
        # I tried gave a sensible answer. Normally I'd be more paranoid due to numpy bloat,
        # but we're calling GDALwarp and passing it filenames, so everything should be done
        # in the C++ world of GDAL, so I have more confidence that we won't see the usual
        # 4x plus memory bloat of loading raster data into the python world.
        match habitat_map.datatype:
            case gdal.GDT_Byte | gdal.GDT_Int8:
                pixel_size = 1
            case gdal.GDT_CInt16 | gdal.GDT_Int16 | gdal.GDT_UInt16:
                pixel_size = 2
            case gdal.GDT_CFloat32 | gdal.GDT_CInt32 | gdal.GDT_Float32 | gdal.GDT_Int32:
                pixel_size = 4
            case _:
                pixel_size = 8
        estimated_memory = pixel_size * pixels

        mem_stats = psutil.virtual_memory()
        max_copies = math.floor((mem_stats.available * 0.5) / estimated_memory)
        if max_copies == 0:
            logger.warning("Low memory")
            max_copies = 1
        process_count = min(max_copies, process_count)
        logger.info("Estimating we can run %s concurrent tasks", process_count)

    # We need to know how many terrains there are. We could get this from the crosswalk
    # table, but we can also work out the unique values ourselves. In practice this is
    # worth the effort, otherwise we generate a lot of empty maps potentially.
    habitats = enumerate_terrain_types(habitat_path)

    if max_copies > 1:
        with Pool(processes=process_count) as pool:
            pool.map(
                partial(make_single_type_map, habitat_path, pixel_scale, target_projection, output_directory_path),
                habitats
            )
    else:
        for habitat in habitats:
            make_single_type_map(habitat_path, pixel_scale, target_projection, output_directory_path, habitat)

def main() -> None:
    parser = argparse.ArgumentParser(description="Downsample habitat map to raster per terrain type.")
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
        required=True,
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
        default=round(cpu_count() / 2),
        dest="processes_count",
        help="Optional number of concurrent threads to use."
    )
    args = parser.parse_args()

    habitat_process(
        args.habitat_path,
        args.pixel_scale,
        args.target_projection,
        args.output_path,
        args.processes_count,
    )

if __name__ == "__main__":
    main()
