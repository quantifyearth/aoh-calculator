import argparse
import json
import os
import sys
from typing import Dict

import numpy as np
import pandas as pd
from fiona.errors import DriverError
from geopandas import gpd
from yirgacheffe.layers import RasterLayer, VectorLayer, ConstantLayer


def load_crosswalk_table(table_file_name: str) -> Dict[str,int]:
	rawdata = pd.read_csv(table_file_name)
	result = dict()
	for _, row in rawdata.iterrows():
		result[row.code] = int(row.value)
	return result

def aohcalc(
	species_id: int,
	results_path: str,
	habitat: str,
	elevation: str,
	range: str,
	info: str,
	crosswalk: str,
) -> None:
	crosswalk_table = load_crosswalk_table(crosswalk)

	os.makedirs(results_path, exist_ok=True)

	species_info = gpd.read_file(info)

	# do we have this species?
	filtered_species_info = species_info[species_info['id_no']==species_id]
	if filtered_species_info.shape[0] == 0:
		raise ValueError(f"Species {species_id} was not in input data")

	# Further filter...
	# TODO
	assert filtered_species_info.shape[0] == 1
	elevation_lower = filtered_species_info.elevation_lower.values[0]
	elevation_upper = filtered_species_info.elevation_upper.values[0]
	raw_habitats = filtered_species_info.full_habitat_code.values[0].split('|')
	habitat_list = [crosswalk_table[float(x)] for x in raw_habitats]

	habitat_map = RasterLayer.layer_from_file(habitat)
	elevation_map = RasterLayer.layer_from_file(elevation)
	range_map = VectorLayer.layer_from_file(info, f'id_no = {species_id}', habitat_map.pixel_scale, habitat_map.projection)

	layers = [habitat_map, elevation_map, range_map]
	intersection = RasterLayer.find_intersection(layers)
	for layer in layers:
		layer.set_window_for_intersection(intersection)
	result_filename = os.path.join(results_path, f"{species_id}.tif")
	result = RasterLayer.empty_raster_layer_like(habitat_map, filename=result_filename)

	filtered_habtitat = habitat_map.numpy_apply(lambda chunk: np.isin(chunk, habitat_list))
	filtered_elevation = elevation_map.numpy_apply(lambda chunk: np.logical_and(chunk >= elevation_lower, chunk <= elevation_upper))

	calc = filtered_habtitat * filtered_elevation * range_map * 255
	calc = calc + (range_map.numpy_apply(lambda chunk: (1 - chunk)) * 128)
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

	try:
		with open(args['config_path'], 'r', encoding='utf-8') as config_file:
			config = json.load(config_file)
	except FileNotFoundError:
		print(f'Failed to find configuration json file {args["config_path"]}', file=sys.stderr)
		sys.exit(1)
	except json.decoder.JSONDecodeError as e:
		print(f'Failed to parse {args["config_path"]} at line {e.lineno}, column {e.colno}: {e.msg}', file=sys.stderr)
		sys.exit(1)

	try:
		aohcalc(
			args['species'],
			args['results_path'],
			**config
		)
	except DriverError as exc:
		print(exc.args[0], file=sys.stderr)
		sys.exit(1)
	except ValueError as exc:
		print(exc.msg, file=sys.stderr)
		sys.exit(1)
	except FileNotFoundError as exc:
		print(f"Failed to find {exc.filename}: {exc.strerror}", file=sys.stderr)
		sys.exit()


if __name__ == "__main__":
	main()
