import argparse
import math
import os
import sys
from typing import Dict, List, Optional


# import pyshark # pylint: disable=W0611
import numpy as np
import pandas as pd
from geopandas import gpd
from yirgacheffe.layers import RasterLayer, VectorLayer, ConstantLayer, UniformAreaLayer
from alive_progress import alive_bar
from osgeo import gdal
gdal.UseExceptions()


def load_crosswalk_table(table_file_name: str) -> Dict[str,List[int]]:
    rawdata = pd.read_csv(table_file_name)
    result = {}
    for _, row in rawdata.iterrows():
        try:
            result[row.code].append(int(row.value))
        except KeyError:
            result[row.code] = [int(row.value)]
    return result

def crosswalk_habitats(crosswalk_table: Dict[str, int], raw_habitats: List) -> List:
    result = []
    for habitat in raw_habitats:
        try:
            hab = float(habitat)
        except ValueError:
            continue
        try:
            crosswalked_habatit = crosswalk_table[hab]
        except KeyError:
            continue
        result += crosswalked_habatit
    return result

def aohcalc(
    habitat_path: str,
    min_elevation_path: str,
    max_elevation_path: str,
    area_path: Optional[str],
    crosswalk_path: str,
    species_data_path: str,
    output_directory_path: str,
) -> None:
    os.makedirs(output_directory_path, exist_ok=True)

    crosswalk_table = load_crosswalk_table(crosswalk_path)

    os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"
    try:
        filtered_species_info = gpd.read_file(species_data_path)
    except: # pylint:disable=W0702
        print(f"Failed to read {species_data_path}", file=sys.stderr)
        sys.exit(1)
    assert filtered_species_info.shape[0] == 1

    try:
        elevation_lower = math.floor(float(filtered_species_info.elevation_lower.values[0]))
        elevation_upper = math.ceil(float(filtered_species_info.elevation_upper.values[0]))
        raw_habitats = filtered_species_info.full_habitat_code.values[0].split('|')
    except (AttributeError, TypeError):
        print(f"Species data missing one or more needed attributes: {filtered_species_info}", file=sys.stderr)
        sys.exit()

    habitat_list = crosswalk_habitats(crosswalk_table, raw_habitats)

    species_id = filtered_species_info.id_no.values[0]
    seasonality = filtered_species_info.seasonal.values[0]

    habitat_maps = [RasterLayer.layer_from_file(os.path.join(habitat_path, f"lcc_{x}.tif")) for x in habitat_list]

    min_elevation_map = RasterLayer.layer_from_file(min_elevation_path)
    max_elevation_map = RasterLayer.layer_from_file(max_elevation_path)
    range_map = VectorLayer.layer_from_file_like(
        species_data_path,
        None,
        min_elevation_map
    )

    area_map = None
    if area_path:
        area_map = UniformAreaLayer.layer_from_file(area_path)

    result_filename = os.path.join(output_directory_path, f"{species_id}_{seasonality}.tif")

    layers = habitat_maps + [min_elevation_map, max_elevation_map, range_map]
    if area_map:
        layers.append(area_map)
    try:
        intersection = RasterLayer.find_intersection(layers)
    except ValueError:
        print(f"Failed to find intersection for {species_data_path}: {range_map.area}")
        print("Just using range")

        result = RasterLayer.empty_raster_layer_like(
            range_map,
            filename=result_filename,
            compress=True,
            nodata=2,
            nbits=2
        )
        b = result._dataset.GetRasterBand(1) # pylint:disable=W0212
        b.SetMetadataItem('NBITS', '2', 'IMAGE_STRUCTURE')
        with alive_bar(manual=True) as bar:
            range_map.save(result, callback=bar)
        sys.exit()

    for layer in layers:
        layer.set_window_for_intersection(intersection)

    result = RasterLayer.empty_raster_layer_like(
        min_elevation_map,
        filename=result_filename,
        compress=True,
        datatype=gdal.GDT_Byte,
        nodata=2,
        nbits=2
    )
    b = result._dataset.GetRasterBand(1) # pylint:disable=W0212
    b.SetMetadataItem('NBITS', '2', 'IMAGE_STRUCTURE')

    if habitat_list:
        combined_habitat = habitat_maps[0]
        for map_layer in habitat_maps[1:]:
            combined_habitat = combined_habitat + map_layer
        combined_habitat = combined_habitat.numpy_apply(lambda c: np.where(c > 1, 1, c))
        filtered_by_habtitat = range_map * combined_habitat
        if filtered_by_habtitat.sum() == 0:
            filtered_by_habtitat = range_map
    else:
        filtered_by_habtitat = range_map

    filtered_elevation = (min_elevation_map.numpy_apply(lambda chunk: chunk <= elevation_upper) *
        max_elevation_map.numpy_apply(lambda chunk: chunk >= elevation_lower))
    filtered_by_both = filtered_elevation * filtered_by_habtitat
    if filtered_by_both.sum() == 0:
        filtered_by_both = filtered_by_habtitat

    if area_map:
        calc = filtered_by_both * area_map
    else:
        calc = filtered_by_both

    with alive_bar(manual=True) as bar:
        calc.save(result, callback=bar)

def main() -> None:
    parser = argparse.ArgumentParser(description="Area of habitat calculator.")
    parser.add_argument(
        '--habitats',
        type=str,
        help="Directory of habitat rasters, one per habitat class.",
        required=True,
        dest="habitat_path"
    )
    parser.add_argument(
        '--elevation-min',
        type=str,
        help="Minimum elevation raster.",
        required=True,
        dest="min_elevation_path",
    )
    parser.add_argument(
        '--elevation-max',
        type=str,
        help="Maximum elevation raster",
        required=True,
        dest="max_elevation_path",
    )
    parser.add_argument(
        '--area',
        type=str,
        help="Optional area per pixel raster. Can be 1xheight.",
        required=False,
        dest="area_path",
    )
    parser.add_argument(
        '--crosswalk',
        type=str,
        help="Path of habitat crosswalk table.",
        required=True,
        dest="crosswalk_path",
    )
    parser.add_argument(
        '--speciesdata',
        type=str,
        help="Single species/seasonality geojson.",
        required=True,
        dest="species_data_path"
    )
    parser.add_argument(
        '--output_directory',
        type=str,
        help='Directory where area geotiffs should be stored.',
        required=True,
        dest='output_path',
    )
    args = parser.parse_args()

    aohcalc(
        args.habitat_path,
        args.min_elevation_path,
        args.max_elevation_path,
        args.area_path,
        args.crosswalk_path,
        args.species_data_path,
        args.output_path
    )

if __name__ == "__main__":
    main()
