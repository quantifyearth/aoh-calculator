import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import yirgacheffe as yg
from shapely.geometry import mapping, Polygon

from aoh.validation.validate_occurences import process_species

def test_empty_species_list() -> None:
    df = pd.DataFrame([], columns=['iucn_taxon_id', 'decimalLatitude', 'decimalLongitude'])
    res = process_species(Path("/some/aohs"), df)
    assert len(res) == 0

def generate_faux_aoh(filename: Path, shape: Polygon | None = None) -> None:

    shapes = {'area': shape if shape is not None else Polygon([(0, 0), (0, 10), (10, 10), (10, 0)])}

    features = []
    for name, geom in shapes.items():
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

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        geojson_path = tmpdir_path / "tmp.geojson"
        with open(geojson_path, 'w', encoding="UTF-8") as f:
            json.dump(geojson, f, indent=2)

        with yg.read_shape(geojson_path, ("epsg:4326", (1.0, -1.0))) as shape_layer:
            shape_layer.to_geotiff(filename)

@pytest.mark.parametrize("taxon_id,latitude,longitude,expected",[
    (42, 5.0, 5.0, True),
    (42, 12.0, 12.0, False),
    (40, 5.0, 5.0, False),
])
def test_simple_match(taxon_id: int, latitude: float, longitude: float, expected: bool) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        for test_id in [41, 42, 43]:
            aoh_path = tmpdir_path / f"{test_id}.tif"
            generate_faux_aoh(aoh_path)

        df = pd.DataFrame(
            [(taxon_id, latitude, longitude)],
            columns=['iucn_taxon_id', 'decimalLatitude', 'decimalLongitude']
        )

        res = process_species(tmpdir_path, df)

        assert len(res) == len(df)
        occurence = res.occurence[0]
        assert occurence == expected

def test_multiple_match() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        for test_id in [41, 42, 43]:
            aoh_path = tmpdir_path / f"{test_id}.tif"
            generate_faux_aoh(aoh_path)

        df = pd.DataFrame(
            [
                (42, 5.0, 5.0, True),
                (42, 12.0, 12.0, False),
            ],
            columns=['iucn_taxon_id', 'decimalLatitude', 'decimalLongitude', 'expected']
        )

        res = process_species(tmpdir_path, df)

        assert len(res) == len(df)
        assert (res.occurence == res.expected).all()

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
        _ = process_species(Path("/some/aohs"), df)

@pytest.mark.parametrize("taxon_id,latitude,longitude,expected",[
    (42, 5.0, 5.0, True),
    (42, -5.0, -5.0, True),
    (42, 5.0, -5.0, False),
    (42, -5.0, 5.0, False),
    (40, 5.0, 5.0, False),
])
def test_find_seasonal(taxon_id: int, latitude: float, longitude: float, expected: bool) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        for season, shape in [
            ('breeding', Polygon([(0, 0), (0, 10), (10, 10), (10, 0)])),
            ('nonbreeding', Polygon([(0, 0), (0, -10), (-10, -10), (-10, 0)])),
        ]:
            aoh_path = tmpdir_path / f"42_{season}.tif"
            generate_faux_aoh(aoh_path, shape)

        df = pd.DataFrame(
            [(taxon_id, latitude, longitude)],
            columns=['iucn_taxon_id', 'decimalLatitude', 'decimalLongitude']
        )

        res = process_species(tmpdir_path, df)

        assert len(res) == len(df)
        occurence = res.occurence[0]
        assert occurence == expected
