import tempfile
from pathlib import Path
from typing import Set, Tuple

import numpy as np
import yirgacheffe as yg
from osgeo import gdal

from habitat_process import enumerate_terrain_types, _make_single_type_map

def generate_habitat_map(
    output_path: Path,
    dimensions: Tuple[int,int],
    options: Set[int],
) -> None:
    width, height = dimensions
    data = np.random.choice(list(options), size=(height, width))
    dataset = gdal.GetDriverByName("GTiff").Create(
        output_path,
        width,
        height,
        1,
        gdal.GDT_Int16,
        [],
    )
    dataset.SetGeoTransform((-180.0, 360/width, 0.0, 90, 0.0, -180/height))
    dataset.SetProjection("WGS84")
    band = dataset.GetRasterBand(1)
    band.WriteArray(data, 0, 0)
    dataset.Close()

def test_enumaerate_subset() -> None:
    options = {0, 100, 200, 300}
    with tempfile.TemporaryDirectory() as tempdir:
        habitat_path = Path(tempdir) / "habitat.tif"
        generate_habitat_map(habitat_path, (20, 10), options)
        assert habitat_path.exists()
        result = enumerate_terrain_types(habitat_path)
    # Zero values are removed
    assert result == {100, 200, 300}

def test_simple_make_single_map() -> None:
    options = {100, 200}
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)
        habitat_path = tmp / "habitat.tif"
        generate_habitat_map(habitat_path, (20, 10), options)
        assert habitat_path.exists()

        _make_single_type_map(
            habitat_path,
            None,
            None,
            tmp,
            100,
        )
        expected_result_path = tmp / "lcc_100.tif"
        assert expected_result_path.exists()

        with  yg.read_raster(habitat_path) as original:
            with yg.read_raster(expected_result_path) as result:
                assert result.window == original.window
                original_data = original.read_array(0, 0, original.window.xsize, original.window.ysize)
                result_data = result.read_array(0, 0, result.window.xsize, result.window.ysize)

        # We did not resize or projection, so should be just a simple map
        expected_data = (original_data == 100).astype(int)
        assert expected_data.sum() != (20 * 10) # Wasn't all the same value
        assert (expected_data == result_data).all()

def test_rescale_make_single_map() -> None:
    options = {100, 200}
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)
        habitat_path = tmp / "habitat.tif"
        generate_habitat_map(habitat_path, (20, 10), options)
        assert habitat_path.exists()

        _make_single_type_map(
            habitat_path,
            180.0 / 5.0, # Scale down by half
            None,
            tmp,
            100,
        )
        expected_result_path = tmp / "lcc_100.tif"
        assert expected_result_path.exists()

        with  yg.read_raster(habitat_path) as original:
            with yg.read_raster(expected_result_path) as result:
                assert result.window.xsize == original.window.xsize / 2
                assert result.window.ysize == original.window.ysize / 2
                original_data = original.read_array(0, 0, original.window.xsize, original.window.ysize)
                result_data = result.read_array(0, 0, result.window.xsize, result.window.ysize)

        binary_original_data = (original_data == 100).astype(int)
        expected_data = binary_original_data.reshape(5, 2, 10, 2).mean(axis=(1, 3))
        assert (expected_data == result_data).all()
