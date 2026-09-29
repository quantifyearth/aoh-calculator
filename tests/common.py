from pathlib import Path

import geojson # type: ignore
import geopandas as gpd
import numpy as np
import pandas as pd
from osgeo import gdal # type: ignore
from shapely.geometry import shape

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

def generate_constant_map(
    output_path: Path,
    dimensions: tuple[int, int],
    value: float,
) -> None:
    width, height = dimensions
    data = np.full((height, width), value)
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

def generate_species_info(
    output_path: Path,
    elevation_range: tuple[int,int],
    habitat_codes: set[str],
) -> None:
    properties = {
        "id_no": "1234",
        "assessment_id": "789",
        "season": "resident",
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
        geojson.dump(feature, f)

def generate_multi_species(
    output_path: Path,
    per_species_info_and_scale: list[tuple[dict[str,str|float],float]],
) -> None:
    features = []
    print(per_species_info_and_scale)
    for idx, info_and_scale in enumerate(per_species_info_and_scale):
        print(info_and_scale)
        info, scale = info_and_scale
        properties = {
            "id_no": str(idx),
            "assessment_id": str(idx),
            "season": "resident",
            **info
        }
        coordinates = [[
            [-90 * scale, -45 * scale],
            [90 * scale, -45 * scale],
            [90 * scale, 45 * scale],
            [-90 * scale, 45 * scale],
            [-90 * scale, -45 * scale],
        ]]
        polygon = geojson.Polygon(coordinates)
        feature = geojson.Feature(geometry=polygon, properties=properties)
        features.append(feature)
    collection = geojson.FeatureCollection(features)

    match output_path.suffix.lower():
        case ".gpkg":
            geometry = [shape(f["geometry"]) for f in collection["features"]]
            rows = [f["properties"] for f in collection["features"]]
            gdf = gpd.GeoDataFrame(rows, geometry=geometry, crs="EPSG:4326")
            gdf.to_file(output_path, driver="GPKG")
        case ".geojson":
            with open(output_path, "w", encoding="UTF-8") as f:
                geojson.dump(collection, f)
        case _:
            assert False

def generate_vector_mask(output_path: Path, coordinates: list[list[list[int]]]) -> None:
    polygon = geojson.Polygon(coordinates)
    feature= geojson.Feature(geometry=polygon)
    with open(output_path, "w", encoding="UTF-8") as f:
        geojson.dump(feature, f)
