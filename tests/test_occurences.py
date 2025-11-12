import json
import math
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import yirgacheffe as yg
from shapely.geometry import mapping, Polygon

from aoh.validation.validate_occurences import process_species

def generate_occurrence_cluster(
    latitude: float,
    longitude: float,
    count: int,
    radius: float,
) -> list[tuple[float,float]]:
    res = [(latitude, longitude)]
    rotation = (math.pi * 2) / (count - 1)
    for i in range(count - 1):
        angle = i * rotation
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        res.append((latitude + y, longitude + x))
    return res

def geojson_of_shaps(shapes):
    features = []
    for geom in shapes:
        feature = {
            "type": "Feature",
            "properties": {},
            "geometry": mapping(geom)
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    return geojson

def generate_faux_aoh(filename: Path, aoh_radius:float=5.0, range_radius:float=10.0) -> None:
    aoh_shapes = [
        Polygon([
            (-aoh_radius, aoh_radius),
            (aoh_radius, aoh_radius),
            (aoh_radius, -aoh_radius),
            (-aoh_radius, -aoh_radius)
        ])
    ]
    aoh_area = sum(x.area for x in aoh_shapes)

    range_shapes = [
        Polygon([
            (-range_radius, range_radius),
            (range_radius, range_radius),
            (range_radius, -range_radius),
            (-range_radius, -range_radius)
        ])
    ]
    range_area = sum(x.area for x in range_shapes)

    assert aoh_area <= range_area

    geojson_path = filename.with_suffix('.geojson')
    with open(geojson_path, 'w', encoding="UTF-8") as f:
        json.dump(geojson_of_shaps(range_shapes), f, indent=2)

    json_path = filename.with_suffix('.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({'prevalence': aoh_area / range_area}, f)

    with tempfile.TemporaryDirectory() as tmpdir:
        aoh_geojson = Path(tmpdir) / "test.geojson"
        with open(aoh_geojson, 'w', encoding="UTF-8") as f:
            json.dump(geojson_of_shaps(aoh_shapes), f, indent=2)
        with yg.read_shape(aoh_geojson, ("epsg:4326", (0.1, -0.1))) as shape_layer:
            shape_layer.to_geotiff(filename)

@pytest.mark.parametrize("taxon_id,latitude,longitude,is_valid,expected_outlier",[
    (42, 0.0, 0.0, True, False), # all in AoH
    (42, 0.0, 4.0, True, False), # Most in AOH, a few in range
    (42, 0.0, 6.5, True, True), # Most in range, a few in AOH
    (42, 0.0, 7.5, True, True),  # all in range but not AOH
    (42, 0.0, 11.0, False, None),  # most out of range
    (42, 0.0, 20.0, False, None), # all out of range
])
def test_simple_match_in_out_range(
    taxon_id: int,
    latitude: float,
    longitude: float,
    is_valid: bool,
    expected_outlier: bool,
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        for test_id in [41, 42, 43]:
            aoh_path = tmpdir_path / f"{test_id}.tif"
            generate_faux_aoh(aoh_path)

        occurences = generate_occurrence_cluster(latitude, longitude, 20, 2.0)
        df = pd.DataFrame(
            [(taxon_id, lat, lng) for (lat, lng) in occurences],
            columns=['iucn_taxon_id', 'decimalLatitude', 'decimalLongitude']
        )
        result = process_species(tmpdir_path, tmpdir_path, df)
        assert result.iucn_taxon_id == taxon_id
        assert result.total_records == len(occurences)
        assert result.is_valid == is_valid
        assert result.is_outlier == expected_outlier

@pytest.mark.parametrize("taxon_id,latitude,longitude,expected_prev,is_valid,expected_outlier",[
    (42, 0.0, 0.0, 1.0, True, False), # all in AoH
    (42, 0.0, 20.0, None, False, None), # all out of range
])
def test_model_prevalence_of_one(
    taxon_id: int,
    latitude: float,
    longitude: float,
    expected_prev: float,
    is_valid: bool,
    expected_outlier: bool,
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        for test_id in [41, 42, 43]:
            aoh_path = tmpdir_path / f"{test_id}.tif"
            generate_faux_aoh(aoh_path, aoh_radius=5.0, range_radius=5.0)

        occurences = generate_occurrence_cluster(latitude, longitude, 20, 2.0)
        df = pd.DataFrame(
            [(taxon_id, lat, lng) for (lat, lng) in occurences],
            columns=['iucn_taxon_id', 'decimalLatitude', 'decimalLongitude']
        )

        result = process_species(tmpdir_path, tmpdir_path, df)
        assert result.iucn_taxon_id == taxon_id
        assert result.total_records == len(occurences)
        assert result.point_prevalence == expected_prev
        assert result.model_prevalence == 1.0
        assert result.is_valid == is_valid
        assert result.is_outlier == expected_outlier

def test_no_aoh_found() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        for test_id in [41, 42, 43]:
            aoh_path = tmpdir_path / f"{test_id}.tif"
            generate_faux_aoh(aoh_path)

        df = pd.DataFrame(
            [(40, 5.0, 5.0)],
            columns=['iucn_taxon_id', 'decimalLatitude', 'decimalLongitude']
        )
        with pytest.raises(FileNotFoundError):
            _ = process_species(tmpdir_path, tmpdir_path, df)

def test_too_many_ids() -> None:
    df = pd.DataFrame(
        [
            (42, 5.0, 5.0, True),
            (42, 12.0, 12.0, False),
            (40, 5.0, 5.0, False),
        ],
        columns=['iucn_taxon_id', 'decimalLatitude', 'decimalLongitude', 'expected']
    )

    with pytest.raises(ValueError):
        _ = process_species(Path("/some/aohs"), Path("/some/aohs"), df)

def test_find_seasonal() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        for season in ['breeding', 'nonbreeding']:
            aoh_path = tmpdir_path / f"42_{season}.tif"
            generate_faux_aoh(aoh_path)

        df = pd.DataFrame(
            [(42, 5.0, 5.0)],
            columns=['iucn_taxon_id', 'decimalLatitude', 'decimalLongitude']
        )

        with pytest.raises(RuntimeError):
            _ = process_species(tmpdir_path, tmpdir_path, df)

def test_empty_species_list() -> None:
    df = pd.DataFrame([], columns=['iucn_taxon_id', 'decimalLatitude', 'decimalLongitude'])
    with pytest.raises(ValueError):
        _ = process_species(Path("/some/aohs"), Path("/some/aohs"), df)
