import argparse
import json
import math
import os
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

import pandas as pd
from yirgacheffe.layers import RasterLayer, VectorLayer, ConstantLayer, UniformAreaLayer # type: ignore
from geopandas import gpd # type: ignore
from alive_progress import alive_bar # type: ignore
from osgeo import gdal # type: ignore
gdal.UseExceptions()

import yirgacheffe # pylint: disable=C0412,C0413
yirgacheffe.constants.YSTEP = 2048

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')

def load_crosswalk_table(table_file_name: Path) -> Dict[str,List[int]]:
    rawdata = pd.read_csv(table_file_name)
    result : Dict[str,List[int]] = {}
    for _, row in rawdata.iterrows():
        code = str(row.code)
        try:
            result[code].append(int(row.value))
        except KeyError:
            result[code] = [int(row.value)]
    return result

def crosswalk_habitats(crosswalk_table: Dict[str, List[int]], raw_habitats: Set[str]) -> Set[int]:
    result = set()
    for habitat in raw_habitats:
        try:
            crosswalked_habatit = crosswalk_table[habitat]
        except KeyError:
            continue
        result |= set(crosswalked_habatit)
    return result

def aohcalc(
    habitat_path: Path,
    min_elevation_path: Path,
    max_elevation_path: Path,
    area_path: Optional[Path],
    crosswalk_path: Path,
    species_data_path: Path,
    force_habitat: bool,
    output_directory_path: Path,
) -> None:
    os.makedirs(output_directory_path, exist_ok=True)

    crosswalk_table = load_crosswalk_table(crosswalk_path)

    os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"
    try:
        filtered_species_info = gpd.read_file(species_data_path)
    except: # pylint:disable=W0702
        logger.error("Failed to read %s", species_data_path)
        sys.exit(1)
    assert filtered_species_info.shape[0] == 1

    # We drop the geometry as that's a lot of data, more than the raster often
    species_info = filtered_species_info.drop('geometry', axis=1)
    manifest = {k: v[0] for (k, v) in species_info.items()}

    species_id = filtered_species_info.id_no.values[0]
    try:
        seasonality = filtered_species_info.season.values[0]
        result_filename = output_directory_path / f"{species_id}_{seasonality}.tif"
        manifest_filename = output_directory_path / f"{species_id}_{seasonality}.json"
    except AttributeError:
        seasonality = None
        result_filename = output_directory_path / f"{species_id}.tif"
        manifest_filename = output_directory_path / f"{species_id}.json"

    try:
        elevation_lower = math.floor(float(filtered_species_info.elevation_lower.values[0]))
        elevation_upper = math.ceil(float(filtered_species_info.elevation_upper.values[0]))
        raw_habitats = set(filtered_species_info.full_habitat_code.values[0].split('|'))
    except (AttributeError, TypeError):
        logger.error("Species data missing one or more needed attributes: %s", filtered_species_info)
        manifest["error"] = "Species data missing one or more needed attributes"
        with open(manifest_filename, 'w', encoding="utf-8") as f:
            json.dump(manifest, f)
        return

    habitat_list = crosswalk_habitats(crosswalk_table, raw_habitats)
    if force_habitat and len(habitat_list) == 0:
        logger.error("No habitats found in crosswalk! %s_%s had %s", species_id, seasonality, raw_habitats)
        manifest["error"] = "No habitats found in crosswalk"
        with open(manifest_filename, 'w', encoding="utf-8") as f:
            json.dump(manifest, f)
        return

    ideal_habitat_map_files = [habitat_path / f"lcc_{x}.tif" for x in habitat_list]
    habitat_map_files = [x for x in ideal_habitat_map_files if x.exists()]
    if force_habitat and len(habitat_map_files) == 0:
        logger.error("No matching habitat layers found for %s_%s in %s: %s",
                     species_id, seasonality, habitat_path, habitat_list)
        manifest["error"] = "No matching habitat layers found"
        with open(manifest_filename, 'w', encoding="utf-8") as f:
            json.dump(manifest, f)
        return

    habitat_maps = [RasterLayer.layer_from_file(x) for x in habitat_map_files]

    min_elevation_map = RasterLayer.layer_from_file(min_elevation_path)
    max_elevation_map = RasterLayer.layer_from_file(max_elevation_path)
    range_map = VectorLayer.layer_from_file_like(
        species_data_path,
        min_elevation_map
    )

    area_map : Union[ConstantLayer, RasterLayer, UniformAreaLayer] = ConstantLayer(1.0)
    if area_path:
        try:
            area_map = UniformAreaLayer.layer_from_file(area_path)
        except ValueError:
            area_map = RasterLayer.layer_from_file(area_path)


    layers = habitat_maps + [min_elevation_map, max_elevation_map, range_map, area_map]
    try:
        intersection = RasterLayer.find_intersection(layers)
    except ValueError:
        logger.warning("Failed to find intersection for %s: %s",  species_data_path, range_map.area)

        result = RasterLayer.empty_raster_layer_like(
            area_map,
            filename=result_filename,
            compress=True,
        )
        with alive_bar(manual=True) as bar:
            range_total = (range_map * area_map).save(result, and_sum=True, callback=bar)

        manifest.update({
            'range_total': range_total,
            'hab_total': 0,
            'dem_total': 0,
            'aoh_total': range_total,
            'prevalence': 1.0,
            'error': 'Failed to find intersection'
        })
        with open(manifest_filename, 'w', encoding="utf-8") as f:
            json.dump(manifest, f)
        return

    for layer in layers:
        layer.set_window_for_intersection(intersection)

    range_total = (range_map * area_map).sum()

    # Habitat evaluation. In the IUCN Redlist Technical Working Group recommendations, if there are no defined
    # habitats, then we revert to range. If the area of the habitat map filtered by species habitat is zero then we
    # similarly revert to range as the assumption is that there is an error in the habitat coding.
    #
    # However, for methodologies, such as the LIFE biodiversity metric by Eyres et al, where you want to do
    # land use change impact scenarios, this rule doesn't work, as it treats extinction due to land use change as
    # then actually filling the range. This we have the force_habitat flag for this use case.
    if habitat_maps or force_habitat:
        combined_habitat = habitat_maps[0]
        for map_layer in habitat_maps[1:]:
            combined_habitat = combined_habitat + map_layer
        combined_habitat = combined_habitat.clip(max=1.0)
        filtered_by_habtitat = range_map * combined_habitat
        if filtered_by_habtitat.sum() == 0:
            if force_habitat:
                manifest.update({
                    'range_total': range_total,
                    'hab_total': 0,
                    'dem_total': 0,
                    'aoh_total': 0,
                    'prevalence': 0,
                    'error': 'No habitat found and --force-habitat specified'
                })
                with open(manifest_filename, 'w', encoding="utf-8") as f:
                    json.dump(manifest, f)
                return
            else:
                filtered_by_habtitat = range_map
    else:
        filtered_by_habtitat = range_map

    # Elevation evaluation. As per the IUCN Redlist Technical Working Group recommendations, if the elevation
    # filtering of the DEM returns zero, then we ignore this layer on the assumption that there is error in the
    # elevation data. This aligns with the data hygine practices recommended by Busana et al, as implemented
    # in cleaning.py, where any bad values for elevation cause us assume the entire range is valid.
    hab_only_total = (filtered_by_habtitat * area_map).sum()

    filtered_elevation = (min_elevation_map <= elevation_upper) & (max_elevation_map >= elevation_lower)

    dem_only_total = (filtered_elevation * range_map * area_map).sum()

    filtered_by_both = filtered_elevation * filtered_by_habtitat
    if filtered_by_both.sum() == 0:
        filtered_by_both = filtered_by_habtitat

    calc = filtered_by_both * area_map

    with RasterLayer.empty_raster_layer_like(
        min_elevation_map,
        filename=result_filename,
        compress=True,
        datatype=gdal.GDT_Float32
    ) as aoh_raster:
        with alive_bar(manual=True) as bar:
            aoh_total = calc.save(aoh_raster, and_sum=True, callback=bar)

    manifest.update({
        'range_total': range_total,
        'hab_total': hab_only_total,
        'dem_total': dem_only_total,
        'aoh_total': aoh_total,
        'prevalence': (aoh_total / range_total) if range_total else 0,
    })
    with open(manifest_filename, 'w', encoding="utf-8") as f:
        json.dump(manifest, f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Area of habitat calculator.")
    parser.add_argument(
        '--habitats',
        type=Path,
        help="Directory of habitat rasters, one per habitat class.",
        required=True,
        dest="habitat_path"
    )
    parser.add_argument(
        '--elevation-min',
        type=Path,
        help="Minimum elevation raster.",
        required=True,
        dest="min_elevation_path",
    )
    parser.add_argument(
        '--elevation-max',
        type=Path,
        help="Maximum elevation raster",
        required=True,
        dest="max_elevation_path",
    )
    parser.add_argument(
        '--area',
        type=Path,
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
        type=Path,
        help="Single species/seasonality geojson.",
        required=True,
        dest="species_data_path"
    )
    parser.add_argument(
        '--force-habitat',
        help="If set, don't treat an empty habitat layer layer as per IRTWG.",
        dest="force_habitat",
        action='store_true',
    )
    parser.add_argument(
        '--output',
        type=Path,
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
        args.force_habitat,
        args.output_path
    )

if __name__ == "__main__":
    main()
