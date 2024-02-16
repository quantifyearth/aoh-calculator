import argparse
import json
import os
import sys
from typing import Dict, List

import pyshark # pylint: disable=W0611
import numpy as np
import pandas as pd
from geopandas import gpd
from yirgacheffe.layers import RasterLayer, VectorLayer

def load_crosswalk_table(table_file_name: str) -> Dict[str,int]:
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
    species_id: int,
    seasonality: int,
    results_path: str,
    habitat: str,
    elevation: str,
    _species_range: str,
    info: str,
    crosswalk: str,
) -> None:
    crosswalk_table = load_crosswalk_table(crosswalk)

    os.makedirs(results_path, exist_ok=True)

    species_info = gpd.read_file(info)

    # do we have this species?
    filtered_species_info = species_info[species_info['id_no']==species_id][species_info['seasonal']==seasonality]
    if filtered_species_info.shape[0] == 0:
        raise ValueError(f"Species {species_id} was not in input data")

    # Further filter...
    # TODO
    assert filtered_species_info.shape[0] == 1
    elevation_lower = filtered_species_info.elevation_lower.values[0]
    elevation_upper = filtered_species_info.elevation_upper.values[0]
    raw_habitats = filtered_species_info.full_habitat_code.values[0].split('|')
    habitat_list = crosswalk_habitats(crosswalk_table, raw_habitats)
    assert len(habitat_list) > 0, f"No habitat for {species_id} {seasonality}"

    # range_info = gpd.read_file(range)
    # filtered_range_info = range_info[species_info['id_no']==species_id][species_info['seasonal']==seasonality]
    # assert filtered_range_info.shape == filtered_species_info.shape

    habitat_map = RasterLayer.layer_from_file(habitat)
    elevation_map = RasterLayer.layer_from_file(elevation)
    range_map = VectorLayer.layer_from_file_like(
        info,
        f'id_no = {species_id} AND seasonal = {seasonality}',
        habitat_map
    )

    layers = [habitat_map, elevation_map, range_map]
    intersection = RasterLayer.find_intersection(layers)
    for layer in layers:
        layer.set_window_for_intersection(intersection)

    result_filename = os.path.join(results_path, f"{species_id}_{seasonality}.tif")
    result = RasterLayer.empty_raster_layer_like(
        habitat_map,
        filename=result_filename,
        compress=True,
        nodata=2,
        nbits=2
    )
    # b = result._dataset.GetRasterBand(1)
    # b.SetMetadataItem('NBITS', '2', 'IMAGE_STRUCTURE')

    try:
        filtered_habtitat = habitat_map.numpy_apply(lambda chunk: np.isin(chunk, habitat_list))
    except ValueError:
        print(habitat_list)
        assert False
    filtered_elevation = elevation_map.numpy_apply(
        lambda chunk: np.logical_and(chunk >= elevation_lower, chunk <= elevation_upper)
    )

    calc = filtered_habtitat * filtered_elevation * range_map
    calc = calc + (range_map.numpy_apply(lambda chunk: (1 - chunk)) * 2)
    calc.save(result)

def main():
    parser = argparse.ArgumentParser(description="Area of habitat calculator.")
    parser.add_argument(
        '--taxid',
        type=int,
        help="animal taxonomy id",
        required=True,
        dest="species"
    )
    parser.add_argument(
        '--seasonality',
        type=int,
        help="Season for migratory species",
        required=True,
        dest="seasonality",
    )
    parser.add_argument(
        '--config',
        type=str,
        help="path of configuration json",
        required=False,
        dest="config_path",
        default="config.json"
    )
    parser.add_argument(
        '--geotiffs',
        type=str,
        help='directory where area geotiffs should be stored',
        required=True,
        dest='results_path',
        default=None,
    )
    args = vars(parser.parse_args())
    print(args)
    try:
        with open(args['config_path'], 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        print(f'Failed to find configuration json file {args["config_path"]}', file=sys.stderr)
        sys.exit(1)
    except json.decoder.JSONDecodeError as e:
        print(f'Failed to parse {args["config_path"]} at line {e.lineno}, column {e.colno}: {e.msg}', file=sys.stderr)
        sys.exit(1)

    aohcalc(
        args['species'],
        args['seasonality'],
        args['results_path'],
        **config
    )

if __name__ == "__main__":
    main()
