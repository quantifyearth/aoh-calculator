import json
import math
import tempfile
from pathlib import Path

import geojson # type: ignore
import numpy as np
import pandas as pd
import pytest
import yirgacheffe as yg
from osgeo import gdal # type: ignore

from aoh import aohcalc_binary

def generate_habitat_map(
    output_path: Path,
    dimensions: tuple[int,int],
    options: set[int],
) -> None:
    width, height = dimensions
    # list of set is not stable, so must be ordered
    options_list = sorted(list(options))
    data = np.array(options_list * ((width * height) // len(options_list) + 1))[:width * height]
    data = data.reshape(height, width)
    dataset = gdal.GetDriverByName("GTiff").Create(
        output_path,
        width,
        height,
        1,
        gdal.GDT_Float64,
        [],
    )
    dataset.SetGeoTransform((-180.0, 360/width, 0.0, 90, 0.0, -180/height))
    dataset.SetProjection("WGS84")
    band = dataset.GetRasterBand(1)
    band.WriteArray(data, 0, 0)
    dataset.Close()

def generate_flat_elevation_map(
    output_path: Path,
    dimensions: tuple[int, int],
    elevation_value: int,
) -> None:
    width, height = dimensions
    data = np.full((height, width), elevation_value)
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

def generate_area_map(
    output_path: Path,
    dimensions: tuple[int, int],
    area_value: float,
) -> None:
    width, height = dimensions
    data = np.full((height, width), area_value)
    dataset = gdal.GetDriverByName("GTiff").Create(
        output_path,
        width,
        height,
        1,
        gdal.GDT_Float32,
        [],
    )
    dataset.SetGeoTransform((-180.0, 360/width, 0.0, 90, 0.0, -180/height))
    dataset.SetProjection("WGS84")
    band = dataset.GetRasterBand(1)
    band.WriteArray(data, 0, 0)
    dataset.Close()

def generate_crosswalk(
    output_path: Path,
    values: dict[str,set[int]],
) -> None:
    res = []
    for k, v in values.items():
        for x in v:
            res.append([k, x])
    df = pd.DataFrame(res, columns=["code", "value"])
    df.to_csv(output_path, index=False)

def generate_species_info(
    output_path: Path,
    elevation_range: tuple[int,int],
    habitat_codes: set[str],
) -> None:
    properties = {
        "id_no": "1234",
        "season": "1",
        "elevation_lower": float(elevation_range[0]),
        "elevation_upper": float(elevation_range[1]),
        "full_habitat_code": "|".join(sorted(list(habitat_codes))),
    }
    coordinates = [[
        [-90, -45],
        [90, -45],
        [90, 45],
        [-90, 45],
        [-90, -45],
    ]]
    polygon = geojson.Polygon(coordinates)
    feature= geojson.Feature(geometry=polygon, properties=properties)
    with open(output_path, "w", encoding="UTF-8") as f:
        json.dump(feature, f)

@pytest.mark.parametrize("force_habitat", [True, False])
def test_simple_aoh(force_habitat) -> None:
    dims = (200, 100)

    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitat.tif"
        generate_habitat_map(
            habitats_path,
            dims,
            {100, 200},
        )

        elevation_path = tmp / "elevation.tif"
        generate_flat_elevation_map(elevation_path, dims, 150)

        crosswalk = {
            "1.0": {100, 101, 102},
            "1.1": {100, 101},
            "1.2": {100, 102},
            "2.0": {200, 201},
            "2.1": {200, 201},
        }
        crosswalk_path = tmp / "crosswalk.csv"
        generate_crosswalk(crosswalk_path, crosswalk)

        species_data_path = tmp / "species.geojson"
        generate_species_info(species_data_path, (100, 200), {"1.1"})

        output_dir = tmp / "results"
        aohcalc_binary(
            habitats_path,
            elevation_path,
            crosswalk_path,
            species_data_path,
            output_dir,
            force_habitat=force_habitat,
        )

        expected_geotiff_path = output_dir / "1234_1.tif"
        assert expected_geotiff_path.exists()
        expected_manifest_path = output_dir / "1234_1.json"
        assert expected_manifest_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "1"
        assert manifest["elevation_lower"] == 100
        assert manifest["elevation_upper"] == 200
        assert manifest["full_habitat_code"] == "1.1"

        # Check calculated values. All habitat layers for this
        # test are 50%
        assert manifest["range_total"] == dims[0] * dims[1] * 0.25
        assert manifest["dem_total"] == dims[0] * dims[1] * 0.25
        assert manifest["hab_total"] == dims[0] * dims[1] * 0.25 * 0.5
        assert manifest["aoh_total"] == dims[0] * dims[1] * 0.25 * 0.5
        assert manifest["prevalence"] == 0.5

        with yg.read_raster(expected_geotiff_path) as result:
            assert result.window.xsize == dims[0] / 2
            assert result.window.ysize == dims[1] / 2
            data = result.read_array(0, 0, result.window.xsize, result.window.ysize)
        expected = np.array(
            [1, 0] * ((result.window.xsize * result.window.ysize) // 2)
        )[:result.window.xsize * result.window.ysize]
        expected = expected.reshape(result.window.ysize, result.window.xsize)
        assert (data == expected).all()

@pytest.mark.parametrize("force_habitat", [True, False])
def test_no_habitat_aoh(force_habitat) -> None:
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitats.tif"
        generate_habitat_map(
            habitats_path,
            (20, 10),
            {200},
        )

        elevation_path = tmp / "elevation.tif"
        generate_flat_elevation_map(elevation_path, (20, 10), 150)

        crosswalk = {
            "1.0": {100, 101, 102},
            "1.1": {100, 101},
            "1.2": {100, 102},
            "2.0": {200, 201},
            "2.1": {200, 201},
        }
        crosswalk_path = tmp / "crosswalk.csv"
        generate_crosswalk(crosswalk_path, crosswalk)

        species_data_path = tmp / "species.geojson"
        generate_species_info(species_data_path, (100, 200), {"1.1"})

        output_dir = tmp / "results"
        aohcalc_binary(
            habitats_path,
            elevation_path,
            crosswalk_path,
            species_data_path,
            output_dir,
            force_habitat=force_habitat,
        )

        expected_geotiff_path = output_dir / "1234_1.tif"
        assert expected_geotiff_path.exists() == (not force_habitat)
        expected_manifest_path = output_dir / "1234_1.json"
        assert expected_manifest_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "1"
        assert manifest["elevation_lower"] == 100
        assert manifest["elevation_upper"] == 200
        assert manifest["full_habitat_code"] == "1.1"

        if force_habitat:
            assert manifest["error"] == "No habitat found and --force-habitat specified"
        else:
            # The default IUCN behaviour is to revert to range if no habitat
            assert manifest["range_total"] == 60
            assert manifest["dem_total"] == 60
            assert manifest["hab_total"] == 60
            assert manifest["aoh_total"] == 60
            assert manifest["prevalence"] == 1

@pytest.mark.parametrize("force_habitat", [True, False])
def test_simple_aoh_area(force_habitat) -> None:
    dims = (200, 200)
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitats.tif"
        generate_habitat_map(
            habitats_path,
            dims,
            {100, 200},
        )

        elevation_path = tmp / "elevation.tif"
        generate_flat_elevation_map(elevation_path, dims, 150)

        crosswalk = {
            "1.0": {100, 101, 102},
            "1.1": {100, 101},
            "1.2": {100, 102},
            "2.0": {200, 201},
            "2.1": {200, 201},
        }
        crosswalk_path = tmp / "crosswalk.csv"
        generate_crosswalk(crosswalk_path, crosswalk)

        species_data_path = tmp / "species.geojson"
        generate_species_info(species_data_path, (100, 200), {"1.1"})

        area_path = tmp / "area.tif"
        pixel_area = 4200000.0
        generate_area_map(area_path, dims, pixel_area)

        output_dir = tmp / "results"
        aohcalc_binary(
            habitats_path,
            elevation_path,
            crosswalk_path,
            species_data_path,
            output_dir,
            force_habitat=force_habitat,
            weight_layer_paths=[area_path],
        )

        expected_geotiff_path = output_dir / "1234_1.tif"
        assert expected_geotiff_path.exists()
        expected_manifest_path = output_dir / "1234_1.json"
        assert expected_manifest_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "1"
        assert manifest["elevation_lower"] == 100
        assert manifest["elevation_upper"] == 200
        assert manifest["full_habitat_code"] == "1.1"

        # Check calculated values. All habitat layers for this
        # test are 50%
        area = dims[0] * dims[1] * 0.25
        assert manifest["range_total"] == pytest.approx(area * pixel_area, rel=1e-7)
        assert manifest["dem_total"] == pytest.approx(area * pixel_area, rel=1e-7)
        assert manifest["hab_total"] == pytest.approx(area * pixel_area * 0.5, rel=1e-7)
        assert manifest["aoh_total"] == pytest.approx(area * pixel_area * 0.5, rel=1e-7)
        assert manifest["prevalence"] == 0.5

        with yg.read_raster(expected_geotiff_path) as result:
            assert result.window.xsize == dims[0] / 2
            assert result.window.ysize == dims[1] / 2
            data = result.read_array(0, 0, result.window.xsize, result.window.ysize)
        expected = np.array(
            [4200000.0, 0.] * \
            ((result.window.xsize * result.window.ysize) // 2)
        )[:result.window.xsize * result.window.ysize]
        expected = expected.reshape(result.window.ysize, result.window.xsize)
        assert (data == expected).all()

@pytest.mark.parametrize("force_habitat", [True, False])
def test_simple_aoh_multiple_habitats(force_habitat) -> None:
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitat.tif"
        generate_habitat_map(
            habitats_path,
            (20, 10),
            {100, 200, 300, 400},
        )

        elevation_path = tmp / "elevation.tif"
        generate_flat_elevation_map(elevation_path, (20, 10), 150)

        crosswalk = {
            "1.0": {100, 101, 102},
            "1.1": {100, 101},
            "1.2": {100, 102},
            "2.0": {200, 201},
            "2.1": {200, 201},
            "3,0": {300},
        }
        crosswalk_path = tmp / "crosswalk.csv"
        generate_crosswalk(crosswalk_path, crosswalk)

        species_data_path = tmp / "species.geojson"
        generate_species_info(species_data_path, (100, 200), {"1.1", "2.0"})

        output_dir = tmp / "results"
        aohcalc_binary(
            habitats_path,
            elevation_path,
            crosswalk_path,
            species_data_path,
            output_dir,
            force_habitat=force_habitat,
        )

        expected_geotiff_path = output_dir / "1234_1.tif"
        assert expected_geotiff_path.exists()
        expected_manifest_path = output_dir / "1234_1.json"
        assert expected_manifest_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "1"
        assert manifest["elevation_lower"] == 100
        assert manifest["elevation_upper"] == 200
        assert manifest["full_habitat_code"] == "1.1|2.0"

        # Check calculated values. All habitat layers for this
        # test are 50%
        assert manifest["range_total"] == 60
        assert manifest["dem_total"] == 60
        assert math.isclose(manifest["hab_total"], 30)
        assert math.isclose(manifest["aoh_total"], 30)
        assert math.isclose(manifest["prevalence"], 1/2)

        with yg.read_raster(expected_geotiff_path) as result:
            assert result.window.xsize == 10
            assert result.window.ysize == 6
            data = result.read_array(0, 0, 10, 6)

        expected = np.array([1, 0, 0, 1, 1, 0, 0, 1, 1, 0] * 6)
        expected = expected.reshape(result.window.ysize, result.window.xsize)
        assert np.isclose(data, expected).all()


@pytest.mark.parametrize("force_habitat", [True, False])
def test_no_overlapping_habitats(force_habitat) -> None:
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitats.tif"
        generate_habitat_map(
            habitats_path,
            (20, 10),
            {100, 200, 300},
        )

        elevation_path = tmp / "elevation.tif"
        generate_flat_elevation_map(elevation_path, (20, 10), 150)

        crosswalk = {
            "1.0": {100, 101, 102},
            "1.1": {100, 101},
            "1.2": {100, 102},
            "2.0": {200, 201},
            "2.1": {200, 201},
            "3,0": {300},
        }
        crosswalk_path = tmp / "crosswalk.csv"
        generate_crosswalk(crosswalk_path, crosswalk)

        species_data_path = tmp / "species.geojson"
        generate_species_info(species_data_path, (100, 200), {"42.0"})

        output_dir = tmp / "results"
        aohcalc_binary(
            habitats_path,
            elevation_path,
            crosswalk_path,
            species_data_path,
            output_dir,
            force_habitat=force_habitat,
        )

        expected_geotiff_path = output_dir / "1234_1.tif"
        assert expected_geotiff_path.exists() == (not force_habitat)
        expected_manifest_path = output_dir / "1234_1.json"
        assert expected_manifest_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "1"
        assert manifest["elevation_lower"] == 100
        assert manifest["elevation_upper"] == 200
        assert manifest["full_habitat_code"] == "42.0"

        if force_habitat:
            assert manifest["error"] =="No habitats found in crosswalk"
        else:
            # The default IUCN behaviour is to revert to range if no habitat
            assert manifest["range_total"] == 60
            assert manifest["dem_total"] == 60
            assert manifest["hab_total"] == 60
            assert manifest["aoh_total"] == 60
            assert manifest["prevalence"] == 1

@pytest.mark.parametrize("force_habitat", [True, False])
def test_no_elevation_aoh(force_habitat) -> None:
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitats.tif"
        generate_habitat_map(
            habitats_path,
            (20, 10),
            {100, 200, 300},
        )

        elevation_path = tmp / "elevation.tif"
        generate_flat_elevation_map(elevation_path, (20, 10), 150)

        crosswalk = {
            "1.0": {100, 101, 102},
            "1.1": {100, 101},
            "1.2": {100, 102},
            "2.0": {200, 201},
            "2.1": {200, 201},
        }
        crosswalk_path = tmp / "crosswalk.csv"
        generate_crosswalk(crosswalk_path, crosswalk)

        species_data_path = tmp / "species.geojson"
        generate_species_info(species_data_path, (2100, 2200), {"1.1"})

        output_dir = tmp / "results"
        aohcalc_binary(
            habitats_path,
            elevation_path,
            crosswalk_path,
            species_data_path,
            output_dir,
            force_habitat=force_habitat,
        )

        expected_geotiff_path = output_dir / "1234_1.tif"
        assert expected_geotiff_path.exists()
        expected_manifest_path = output_dir / "1234_1.json"
        assert expected_manifest_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "1"
        assert manifest["elevation_lower"] == 2100
        assert manifest["elevation_upper"] == 2200
        assert manifest["full_habitat_code"] == "1.1"

        # The default IUCN behaviour is to revert to range if no elevation
        print(manifest)
        assert manifest["range_total"] == 60
        assert manifest["dem_total"] == 0
        assert manifest["hab_total"] == 20
        assert manifest["aoh_total"] == 20
        assert manifest["prevalence"] == 1 / 3
