import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pytest
import yirgacheffe as yg
from osgeo import gdal # type: ignore

from common import generate_crosswalk, generate_flat_elevation_map, generate_constant_map, generate_species_info, \
    generate_multi_species, generate_vector_mask

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

        expected_manifest_path = output_dir / "aoh_T1234A789_resident.json"
        assert expected_manifest_path.exists()
        expected_geotiff_path = output_dir / "aoh_T1234A789_resident.tif"
        assert expected_geotiff_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "resident"
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
            width, height = result.dimensions
            assert width == dims[0] / 2
            assert height == dims[1] / 2
            data = result.read_array(0, 0, width, height)
        expected = np.array(
            [1, 0] * ((width * height) // 2)
        )[:width * height]
        expected = expected.reshape(height, width)
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

        expected_geotiff_path = output_dir / "aoh_T1234A789_resident.tif"
        assert expected_geotiff_path.exists() == (not force_habitat)
        expected_manifest_path = output_dir / "aoh_T1234A789_resident.json"
        assert expected_manifest_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "resident"
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
def test_simple_aoh_weight(force_habitat) -> None:
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
        generate_constant_map(area_path, dims, pixel_area)

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

        expected_geotiff_path = output_dir / "aoh_T1234A789_resident.tif"
        assert expected_geotiff_path.exists()
        expected_manifest_path = output_dir / "aoh_T1234A789_resident.json"
        assert expected_manifest_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "resident"
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
            width, height = result.dimensions
            assert width == dims[0] / 2
            assert height == dims[1] / 2
            data = result.read_array(0, 0, width, height)
        expected = np.array(
            [4200000.0, 0.] * \
            ((width * height) // 2)
        )[:width * height]
        expected = expected.reshape(height, width)
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

        expected_geotiff_path = output_dir / "aoh_T1234A789_resident.tif"
        assert expected_geotiff_path.exists()
        expected_manifest_path = output_dir / "aoh_T1234A789_resident.json"
        assert expected_manifest_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "resident"
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
            width, height = result.dimensions
            assert width == 10
            assert height == 6
            data = result.read_array(0, 0, 10, 6)

        expected = np.array([1, 0, 0, 1, 1, 0, 0, 1, 1, 0] * 6)
        expected = expected.reshape(height, width)
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

        expected_geotiff_path = output_dir / "aoh_T1234A789_resident.tif"
        assert expected_geotiff_path.exists() == (not force_habitat)
        expected_manifest_path = output_dir / "aoh_T1234A789_resident.json"
        assert expected_manifest_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "resident"
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

        expected_geotiff_path = output_dir / "aoh_T1234A789_resident.tif"
        assert expected_geotiff_path.exists()
        expected_manifest_path = output_dir / "aoh_T1234A789_resident.json"
        assert expected_manifest_path.exists()

        with open(expected_manifest_path, "r", encoding="UTF-8") as f:
            manifest = json.load(f)

        # Check basic facts
        assert manifest["id_no"] == "1234"
        assert manifest["season"] == "resident"
        assert manifest["elevation_lower"] == 2100
        assert manifest["elevation_upper"] == 2200
        assert manifest["full_habitat_code"] == "1.1"

        # The default IUCN behaviour is to revert to range if no elevation
        assert manifest["range_total"] == 60
        assert manifest["dem_total"] == 0
        assert manifest["hab_total"] == 20
        assert manifest["aoh_total"] == 20
        assert manifest["prevalence"] == 1 / 3

def test_simple_aoh_area() -> None:
    dims = (200, 200)
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitats.tif"
        generate_habitat_map(
            habitats_path,
            dims,
            {100, 200},
        )

        min_elevation_path = tmp / "elevation_min.tif"
        generate_flat_elevation_map(min_elevation_path, dims, -200)
        max_elevation_path = tmp / "elevation_max.tif"
        generate_flat_elevation_map(max_elevation_path, dims, 1000)

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

        output_dir_without_area = tmp / "results_without_area"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_without_area,
        )

        output_dir_with_area = tmp / "results_with_area"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_with_area,
            multiply_by_area_per_pixel=True,
        )

        # This is a little circular, but it at least checks the flag works
        expected_area = yg.area_raster(("WGS84", (360/200, -180/200)))

        with (
            yg.read_raster(output_dir_without_area / "aoh_T1234A789_resident.tif") as aoh_sans_area,
            yg.read_raster(output_dir_with_area / "aoh_T1234A789_resident.tif") as aoh_with_area,
        ):
            with open(output_dir_without_area / "aoh_T1234A789_resident.json", "r", encoding="UTF-8") as f:
                sans_area_manifest = json.load(f)
            with open(output_dir_with_area / "aoh_T1234A789_resident.json", "r", encoding="UTF-8") as f:
                with_area_manifest = json.load(f)

            # Check calculated values. All habitat layers for this
            # test are 50%
            expected_sans_area_total = dims[0] * dims[1] * 0.25 * 0.5
            assert aoh_sans_area.sum() == expected_sans_area_total

            assert aoh_sans_area.sum() < aoh_with_area.sum()
            manual_version_total = (aoh_sans_area * expected_area).sum()
            auto_version_total = aoh_with_area.sum()
            assert auto_version_total == manual_version_total

            assert sans_area_manifest["aoh_total"] == aoh_sans_area.sum()
            assert sans_area_manifest["prevalence"] == 0.5
            assert with_area_manifest["aoh_total"] == aoh_with_area.sum()
            assert with_area_manifest["prevalence"] == 0.5 # over small area this should still hold

def test_simple_aoh_area_and_weights() -> None:
    dims = (200, 200)
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitats.tif"
        generate_habitat_map(
            habitats_path,
            dims,
            {100, 200},
        )

        min_elevation_path = tmp / "elevation_min.tif"
        generate_flat_elevation_map(min_elevation_path, dims, -200)
        max_elevation_path = tmp / "elevation_max.tif"
        generate_flat_elevation_map(max_elevation_path, dims, 1000)

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

        output_dir_without_area = tmp / "results_without_area"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_without_area,
        )

        const_path = tmp / "area.tif"
        generate_constant_map(const_path, dims, 2)

        output_dir_with_area = tmp / "results_with_area"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_with_area,
            weight_layer_paths=[const_path],
            multiply_by_area_per_pixel=True,
        )

        # This is a little circular, but it at least checks the flag works
        expected_area = yg.area_raster(("WGS84", (360/200, -180/200)))

        with (
            yg.read_raster(output_dir_without_area / "aoh_T1234A789_resident.tif") as aoh_sans_area,
            yg.read_raster(output_dir_with_area / "aoh_T1234A789_resident.tif") as aoh_with_area,
        ):
            with open(output_dir_with_area / "aoh_T1234A789_resident.json", "r", encoding="UTF-8") as f:
                with_area_manifest = json.load(f)

            manual_version_total = (aoh_sans_area * expected_area * 2).sum()
            auto_version_total = aoh_with_area.sum()
            assert auto_version_total == manual_version_total

            assert with_area_manifest["aoh_total"] == manual_version_total.sum()
            assert with_area_manifest["prevalence"] == 0.5 # over small area this should still hold

@pytest.mark.parametrize("mask_area,overlap", [
    (
        [[
            [-180, -90],
            [0, -90],
            [0, 90],
            [-180, 90],
            [-180, -90],
        ]],
        0.5
    ),
    (
        [[
            [-180, -90],
            [-170, -90],
            [-170, 90],
            [-180, 90],
            [-180, -90],
        ]],
        0
    ),
])
def test_simple_aoh_vector_mask(mask_area,overlap) -> None:
    dims = (200, 200)
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitats.tif"
        generate_habitat_map(
            habitats_path,
            dims,
            {100, 200},
        )

        min_elevation_path = tmp / "elevation_min.tif"
        generate_flat_elevation_map(min_elevation_path, dims, -200)
        max_elevation_path = tmp / "elevation_max.tif"
        generate_flat_elevation_map(max_elevation_path, dims, 1000)

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

        output_dir_without_mask = tmp / "results_without_mask"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_without_mask,
        )

        mask_path = tmp / "mask.geojson"
        generate_vector_mask(mask_path, mask_area)

        output_dir_with_mask = tmp / "results_with_mask"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_with_mask,
            weight_layer_paths=[mask_path],
        )

        with open(output_dir_without_mask / "aoh_T1234A789_resident.json", "r", encoding="UTF-8") as f:
            without_mask_manifest = json.load(f)
        with open(output_dir_with_mask / "aoh_T1234A789_resident.json", "r", encoding="UTF-8") as f:
            with_mask_manifest = json.load(f)

        assert without_mask_manifest["aoh_total"] > 0
        for key in ["range_total", "hab_total", "dem_total", "aoh_total"]:
            assert with_mask_manifest[key] == without_mask_manifest[key] * overlap

        try:
            with (
                yg.read_raster(output_dir_without_mask / "aoh_T1234A789_resident.tif") as aoh_sans_mask,
                yg.read_raster(output_dir_with_mask / "aoh_T1234A789_resident.tif") as aoh_with_mask,
            ):
                sans_mask_version_total = aoh_sans_mask.sum()
                mask_version_total = aoh_with_mask.sum()
                assert mask_version_total == sans_mask_version_total * overlap
        except FileNotFoundError:
            assert overlap == 0

@pytest.mark.parametrize("constant", [42, 3.5, "42", "3.5"])
def test_simple_aoh_constant_weight(constant) -> None:
    dims = (200, 200)
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitats.tif"
        generate_habitat_map(
            habitats_path,
            dims,
            {100, 200},
        )

        min_elevation_path = tmp / "elevation_min.tif"
        generate_flat_elevation_map(min_elevation_path, dims, -200)
        max_elevation_path = tmp / "elevation_max.tif"
        generate_flat_elevation_map(max_elevation_path, dims, 1000)

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

        output_dir_without_mask = tmp / "results_without_mask"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_without_mask,
        )

        output_dir_with_mask = tmp / "results_with_mask"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_with_mask,
            weight_layer_paths=[constant],
        )

        with (
            yg.read_raster(output_dir_without_mask / "aoh_T1234A789_resident.tif") as aoh_sans_mask,
            yg.read_raster(output_dir_with_mask / "aoh_T1234A789_resident.tif") as aoh_with_mask,
        ):
            sans_mask_version_total = aoh_sans_mask.sum()
            mask_version_total = aoh_with_mask.sum()
            assert mask_version_total == sans_mask_version_total * float(constant)

@pytest.mark.parametrize("ext", ["geojson", "gpkg"])
def test_simple_multiple_aoh_area(ext) -> None:
    dims = (200, 200)
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitats.tif"
        generate_habitat_map(
            habitats_path,
            dims,
            {100, 200},
        )

        min_elevation_path = tmp / "elevation_min.tif"
        generate_flat_elevation_map(min_elevation_path, dims, -200)
        max_elevation_path = tmp / "elevation_max.tif"
        generate_flat_elevation_map(max_elevation_path, dims, 1000)

        crosswalk = {
            "1.0": {100, 101, 102},
            "1.1": {100, 101},
            "1.2": {100, 102},
            "2.0": {200, 201},
            "2.1": {200, 201},
        }
        crosswalk_path = tmp / "crosswalk.csv"
        generate_crosswalk(crosswalk_path, crosswalk)

        species_data_path = tmp / f"species.{ext}"
        generate_multi_species(
            species_data_path,
            [({
                "id_no": "1234",
                "assessment_id": "789",
                "elevation_lower": 100.0,
                "elevation_upper": 200.0,
                "full_habitat_code": "1.1",
            }, 1.0)],
        )

        output_dir_without_area = tmp / "results_without_area"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_without_area,
        )

        output_dir_with_area = tmp / "results_with_area"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_with_area,
            multiply_by_area_per_pixel=True,
        )

        # This is a little circular, but it at least checks the flag works
        expected_area = yg.area_raster(("WGS84", (360/200, -180/200)))

        with (
            yg.read_raster(output_dir_without_area / "aoh_T1234A789_resident.tif") as aoh_sans_area,
            yg.read_raster(output_dir_with_area / "aoh_T1234A789_resident.tif") as aoh_with_area,
        ):
            with open(output_dir_without_area / "aoh_T1234A789_resident.json", "r", encoding="UTF-8") as f:
                sans_area_manifest = json.load(f)
            with open(output_dir_with_area / "aoh_T1234A789_resident.json", "r", encoding="UTF-8") as f:
                with_area_manifest = json.load(f)

            # Check calculated values. All habitat layers for this
            # test are 50%
            expected_sans_area_total = dims[0] * dims[1] * 0.25 * 0.5
            assert aoh_sans_area.sum() == expected_sans_area_total

            assert aoh_sans_area.sum() < aoh_with_area.sum()
            manual_version_total = (aoh_sans_area * expected_area).sum()
            auto_version_total = aoh_with_area.sum()
            assert auto_version_total == manual_version_total

            assert sans_area_manifest["aoh_total"] == aoh_sans_area.sum()
            assert sans_area_manifest["prevalence"] == 0.5
            assert with_area_manifest["aoh_total"] == aoh_with_area.sum()
            assert with_area_manifest["prevalence"] == 0.5 # over small area this should still hold

@pytest.mark.parametrize("ext", ["geojson", "gpkg"])
def test_multiple_aoh_areas(ext) -> None:
    dims = (200, 200)
    with tempfile.TemporaryDirectory() as tempdir:
        tmp = Path(tempdir)

        habitats_path = tmp / "habitats.tif"
        generate_habitat_map(
            habitats_path,
            dims,
            {100, 200},
        )

        min_elevation_path = tmp / "elevation_min.tif"
        generate_flat_elevation_map(min_elevation_path, dims, -200)
        max_elevation_path = tmp / "elevation_max.tif"
        generate_flat_elevation_map(max_elevation_path, dims, 1000)

        crosswalk = {
            "1.0": {100, 101, 102},
            "1.1": {100, 101},
            "1.2": {100, 102},
            "2.0": {200, 201},
            "2.1": {200, 201},
        }
        crosswalk_path = tmp / "crosswalk.csv"
        generate_crosswalk(crosswalk_path, crosswalk)

        species_data_path = tmp / f"species.{ext}"
        generate_multi_species(
            species_data_path,
            [
                # valid elevation and habitat
                ({
                    "id_no": "1234",
                    "assessment_id": "789",
                    "elevation_lower": 100.0,
                    "elevation_upper": 200.0,
                    "full_habitat_code": "1.1",
                }, 1.0),
                # valid elevation and habitat smaller
                ({
                    "id_no": "1235",
                    "assessment_id": "790",
                    "elevation_lower": 100.0,
                    "elevation_upper": 200.0,
                    "full_habitat_code": "1.1",
                }, 0.5),
                # invalid elevation (will revert to range), valid habitat
                ({
                    "id_no": "2345",
                    "assessment_id": "1789",
                    "elevation_lower": 1150.0,
                    "elevation_upper": 1300.0,
                    "full_habitat_code": "2.1",
                }, 1.0),
                # invalid elevation and habitat
                ({
                    "id_no": "3456",
                    "assessment_id": "7098",
                    "elevation_lower": 1150.0,
                    "elevation_upper": 1300.0,
                    "full_habitat_code": "3.1",
                }, 1.0),
            ],
        )

        output_dir_without_area = tmp / "results_without_area"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_without_area,
            force_habitat=True,
        )

        output_dir_with_area = tmp / "results_with_area"
        aohcalc_binary(
            habitats_path,
            (min_elevation_path, max_elevation_path),
            crosswalk_path,
            species_data_path,
            output_dir_with_area,
            multiply_by_area_per_pixel=True,
            force_habitat=True,
        )

        # This is a little circular, but it at least checks the flag works
        expected_area = yg.area_raster(("WGS84", (360/200, -180/200)))

        for taxonid, assessmentid, scale, is_valid in [
            ("1234", "789", 1.0, True),
            ("1235", "790", 0.5, True),
            ("2345", "1789", 1.0, True),
            ("3456", "7098", 1.0, False)
        ]:
            stub = f"T{taxonid}A{assessmentid}"
            with open(output_dir_without_area / f"aoh_{stub}_resident.json", "r", encoding="UTF-8") as f:
                sans_area_manifest = json.load(f)
            with open(output_dir_with_area / f"aoh_{stub}_resident.json", "r", encoding="UTF-8") as f:
                with_area_manifest = json.load(f)

            if is_valid:
                with (
                    yg.read_raster(output_dir_without_area / f"aoh_{stub}_resident.tif") as aoh_sans_area,
                    yg.read_raster(output_dir_with_area / f"aoh_{stub}_resident.tif") as aoh_with_area,
                ):
                    # Check calculated values. All habitat layers for this
                    # test are 50%
                    expected_sans_area_total = dims[0] * dims[1] * 0.25 * 0.5 * (scale * scale)
                    assert aoh_sans_area.sum() == expected_sans_area_total

                    assert aoh_sans_area.sum() < aoh_with_area.sum()
                    manual_version_total = (aoh_sans_area * expected_area).sum()
                    auto_version_total = aoh_with_area.sum()
                    assert auto_version_total == manual_version_total

                    assert sans_area_manifest["aoh_total"] == aoh_sans_area.sum()
                    assert sans_area_manifest["prevalence"] == 0.5
                    assert with_area_manifest["aoh_total"] == aoh_with_area.sum()
                    assert with_area_manifest["prevalence"] == 0.5 # over small area this should still hold
            else:
                assert (output_dir_without_area / f"aoh_{stub}_resident.tif").exists() is False
                assert (output_dir_with_area / f"aoh_{stub}_resident.tif").exists() is False
                assert sans_area_manifest["error"] == "No habitats found in crosswalk"
                assert with_area_manifest["error"] == "No habitats found in crosswalk"
