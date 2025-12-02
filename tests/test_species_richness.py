import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
import yirgacheffe as yg

from aoh.summaries.species_richness import species_richness

@pytest.mark.parametrize("processes", [1, 4, 16, 32])
def test_simple_summary_all_pixels_no_overlap(processes) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        dirpath = Path(tmpdir)
        aohs_path = dirpath / "aohs"
        os.makedirs(aohs_path)

        projection = yg.MapProjection("esri:54009", 1.0, -1.0)

        # Make some rasters. these should make a solid grid. the values
        # are all different, but the end layer should just be 1 in each cell.
        for y in range(4):
            for x in range(4):
                val = (y * 4) + x
                data = np.array([[val + 1]])
                with yg.from_array(data, (x, y + 1), projection) as cell:
                    cell.to_geotiff(aohs_path / f"{val}_season.tif")

        result_path = dirpath / "species_richness.tif"
        species_richness(aohs_path, result_path, processes)

        with yg.read_raster(result_path) as result:
            assert result.window == yg.Window(0, 0, 4, 4)
            assert result.area == yg.Area(0, 4, 4, 0, projection)
            expected = np.ones((4,4))
            result_data = result.read_array(0, 0, 4, 4)
            assert (result_data == expected).all()

@pytest.mark.parametrize("processes", [1, 4, 16, 32])
def test_simple_summary_all_pixels_overlap(processes) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        dirpath = Path(tmpdir)
        aohs_path = dirpath / "aohs"
        os.makedirs(aohs_path)

        projection = yg.MapProjection("esri:54009", 1.0, -1.0)

        # Make some rasters. these should make a solid grid. the values
        # are all different, but the end layer should just be 1 in each cell.
        for y in range(4):
            for x in range(4):
                val = (y * 4) + x
                data = np.array([[val + 1]])
                with yg.from_array(data, (0, 1), projection) as cell:
                    cell.to_geotiff(aohs_path / f"{val}_season.tif")

        result_path = dirpath / "species_richness.tif"
        species_richness(aohs_path, result_path, processes)

        with yg.read_raster(result_path) as result:
            assert result.window == yg.Window(0, 0, 1, 1)
            assert result.area == yg.Area(0, 1, 1, 0, projection)
            result_data = result.read_array(0, 0, 1, 1)[0][0]
            assert result_data == (4 * 4)

def test_seasons_are_merged() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        dirpath = Path(tmpdir)
        aohs_path = dirpath / "aohs"
        os.makedirs(aohs_path)

        projection = yg.MapProjection("esri:54009", 1.0, -1.0)

        for season in ["breeding", "nonbreeding"]:
            data = np.array([[1]])
            with yg.from_array(data, (0, 1), projection) as cell:
                cell.to_geotiff(aohs_path / f"42_{season}.tif")

        result_path = dirpath / "species_richness.tif"
        species_richness(aohs_path, result_path, 1)

        with yg.read_raster(result_path) as result:
            assert result.window == yg.Window(0, 0, 1, 1)
            assert result.area == yg.Area(0, 1, 1, 0, projection)
            result_data = result.read_array(0, 0, 1, 1)[0][0]
            assert result_data == 1

def test_simple_summary_gaps() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        dirpath = Path(tmpdir)
        aohs_path = dirpath / "aohs"
        os.makedirs(aohs_path)

        projection = yg.MapProjection("esri:54009", 1.0, -1.0)

        # Make some rasters. these should make a solid grid. the values
        # are all different, but the end layer should just be 1 in each cell.
        for y in range(4):
            for x in range(4):
                val = (y * 4) + x
                data = np.array([[val % 2]])
                with yg.from_array(data, (x, y + 1), projection) as cell:
                    cell.to_geotiff(aohs_path / f"{val}_season.tif")

        result_path = dirpath / "species_richness.tif"
        species_richness(aohs_path, result_path, 1)

        with yg.read_raster(result_path) as result:
            assert result.window == yg.Window(0, 0, 4, 4)
            assert result.area == yg.Area(0, 4, 4, 0, projection)
            expected = np.array([
                [0, 1, 0, 1],
                [0, 1, 0, 1],
                [0, 1, 0, 1],
                [0, 1, 0, 1],
            ]).astype(float)
            expected[expected==0] = np.nan
            print(expected)
            result_data = result.read_array(0, 0, 4, 4)
            print(result_data)
            assert np.allclose(result_data, expected, equal_nan=True)
