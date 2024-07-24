import argparse
import math
import os
import shutil
import tempfile
from functools import partial
from multiprocessing import Pool, cpu_count
from typing import Optional

import numpy as np
from osgeo import gdal
from yirgacheffe.layers import RasterLayer  # type: ignore

from aohcalc import load_crosswalk_table

def make_single_type_map(
    habitat_path: str,
    pixel_scale: float,
    target_projection: str,
    output_directory_path: str,
    habitat_value: int | float,
) -> None:
    habitat_map = RasterLayer.layer_from_file(habitat_path)

    # We could do this via yirgacheffe if it wasn't for the need to
    # both rescale and reproject. So we do the initial filtering
    # in that, but then bounce it to a temporary file for the
    # warping
    with tempfile.TemporaryDirectory() as tmpdir:
        filtered_file_name = os.path.join(tmpdir, f"filtered_{habitat_value}.tif")
        calc = habitat_map.numpy_apply(lambda c: c == habitat_value)
        filtered_map = RasterLayer.empty_raster_layer_like(habitat_map, filename=filtered_file_name)
        calc.save(filtered_map)
        filtered_map.close()

        filename = f"habitat_{habitat_value}.tif"
        tempname = os.path.join(tmpdir, filename)
        gdal.Warp(tempname, filtered_file_name, options=gdal.WarpOptions(
            multithread=True,
            dstSRS=target_projection,
            outputType=gdal.GDT_Float32,
            xRes=pixel_scale,
            yRes=0.0 - pixel_scale,
        ))

        shutil.move(tempname, os.path.join(output_directory_path, filename))


def habitat_process(
    habitat_path: str,
    crosswalk_path: Optional[str],
    pixel_scale: float,
    target_projection: str,
    output_directory_path: str,
    process_count: int
) -> None:
    os.makedirs(output_directory_path, exist_ok=True)

    habitat_map = RasterLayer.layer_from_file(habitat_path)

    # Step one, we need to know how many terrains there are. We could get this from the crosswalk
    # table, but we can also work out the unique values ourselves
    habitats = set()
    if crosswalk_path:
        crosswalk_table = load_crosswalk_table(crosswalk_path)
        habitats = set(sum(crosswalk_table.values(), []))
    else:
        print("Calculating habitat list from habitat map - this may be quite slow.")
        calc = habitat_map.numpy_apply(lambda c: habitats.update(set(np.unique(c))) or 0)
        calc.sum()
        habitat_map.close()
        del habitat_map
    print(f"Habitat list: {habitats}")

    with Pool(processes=process_count) as pool:
        pool.map(
            partial(make_single_type_map, habitat_path, pixel_scale, target_projection, output_directory_path),
            habitats
        )

def main() -> None:
    parser = argparse.ArgumentParser(description="Downsample habitat map to raster per terrain type.")
    parser.add_argument(
        '--habitat',
        type=str,
        help="Initial habitat.",
        required=True,
        dest="habitat_path"
    )
    parser.add_argument(
        '--crosswalk',
        type=str,
        help="habitat crosswalk table path",
        required=False,
        dest="crosswalk_path",
    )
    parser.add_argument(
        "--scale",
        type=float,
        required=True,
        dest="pixel_scale",
        help="Output pixel scale value."
    )
    parser.add_argument(
        '--projection',
        type=str,
        help="Target projection",
        required=False,
        dest="target_projection",
        default="ESRI:54017"
    )
    parser.add_argument(
        "--output",
        type=str,
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
        help="Number of concurrent threads to use."
    )
    args = parser.parse_args()

    habitat_process(
        args.habitat_path,
        args.crosswalk_path,
        args.pixel_scale,
        args.target_projection,
        args.output_path,
        args.processes_count,
    )

if __name__ == "__main__":
    main()
