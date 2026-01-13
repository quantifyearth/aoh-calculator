import os
from pathlib import Path

import yirgacheffe as yg
from alive_progress import alive_bar # type: ignore

from .speciesinfo import SpeciesInfo

def aohcalc_simple(
    habitat_path: Path,
    elevation_path: Path,
    crosswalk_path: Path,
    species_data_path: Path,
    output_directory_path: Path,
    weight_layer_paths: list[Path]=[],
    force_habitat: bool=False,
) -> None:
    """An implementation of the AOH method from Brooks et al.

    Note, all rasters must be in the same projection and pixel scale.

    Arguments:
        habitat_path: Path of the land cover or habitat map raster.
        elevation_path: Path of the DEM raster.
        crosswalk_path: Path to a CSV file which contains mapping of IUCN habitat class to values in the land cover or habitat map.
        species_data_path: Path to a GeoJSON containing the data for a given species. See README.md for format.
        output_directory_path: Directory into which the output GeoTIFF raster and summary JSON file will be written.
        weight_layer_paths: An optional list of rasters that will be multiplied by the generated raster.
        force_habitat: If true, do not revert to range if habitat layer contains no valid pixels.

        Common uses:

        - **Area correction**: Pass a raster of pixel areas in square meters
          to convert from pixel counts to actual area (important for
          geographic coordinate systems like WGS84)
        - **Spatial masking**: Pass a binary raster to clip results to
          land areas or other regions of interest

    Examples
    --------
    # Area correction for WGS84
    calculate_aoh(..., multipliers=pixel_area_raster)

    # Mask to land and apply area correction
    calculate_aoh(..., multipliers=[land_mask, pixel_area_raster])
    """

    os.makedirs(output_directory_path, exist_ok=True)

    species_info = SpeciesInfo(species_data_path, crosswalk_path)

    try:
        elevation_lower = species_info.elevation_lower
        elevation_upper = species_info.elevation_upper
    except (AttributeError, TypeError):
        logger.error("Species data missing one or more needed attributes")
        species_info.save_manifest(output_directory_path, "Species data missing one or more needed attributes")
        return

    habitat_list = species_info.habitat_list
    if force_habitat and len(habitat_list) == 0:
        logger.error("No habitats found in crosswalk! %s_%s had %s", species_info.species_id, species_info.season, species_info.raw_habitats)
        species_info.save_manifest(output_directory_path, "No habitats found in crosswalk")
        return


    habitat_map = yg.read_raster(habitat_path)
    elevation_map = yg.read_raster(elevation_path)
    range_map = yg.read_shape_like(
        species_data_path,
        elevation_map,
        datatype=yg.DataType.Float32,
    )

    area_map : float | yg.YirgacheffeLayer = 1.0
    if weight_layer_paths:
        try:
            area_map = yg.read_narrow_raster(area_path)
        except ValueError:
            area_map = yg.read_raster(area_path)

    range_total = (range_map * area_map).sum()

    # We've had instances of overflow issues with large ranges in the past
    assert range_total >= 0.0

    # Habitat evaluation. In the IUCN Redlist Technical Working Group recommendations, if there are no defined
    # habitats, then we revert to range. If the area of the habitat map filtered by species habitat is zero then we
    # similarly revert to range as the assumption is that there is an error in the habitat coding.
    #
    # However, for methodologies, such as the LIFE biodiversity metric by Eyres et al, where you want to do
    # land use change impact scenarios, this rule doesn't work, as it treats extinction due to land use change as
    # then actually filling the range. This we have the force_habitat flag for this use case.

    combined_habitat = habitat_map.isin(species_info.habitat_list)
    filtered_by_habtitat = range_map * combined_habitat
    if filtered_by_habtitat.sum() == 0:
        if force_habitat:
            species_info.update_manifest({
                'range_total': range_total,
                'hab_total': 0.0,
                'dem_total': 0.0,
                'aoh_total': 0.0,
                'prevalence': 0.0,
                'error': 'No habitat found and --force-habitat specified'
            })
            species_info.save_manifest(output_directory_path)
            return
        else:
            filtered_by_habtitat = range_map

    # Elevation evaluation. As per the IUCN Redlist Technical Working Group recommendations, if the elevation
    # filtering of the DEM returns zero, then we ignore this layer on the assumption that there is error in the
    # elevation data. This aligns with the data hygine practices recommended by Busana et al, as implemented
    # in cleaning.py, where any bad values for elevation cause us assume the entire range is valid.
    hab_only_total = (filtered_by_habtitat * area_map).sum()

    filtered_elevation = (elevation_map <= elevation_upper) & (elevation_map >= elevation_lower)

    dem_only_total = (filtered_elevation * range_map * area_map).sum()

    filtered_by_both = filtered_elevation * filtered_by_habtitat
    if filtered_by_both.sum() == 0:
        filtered_by_both = filtered_by_habtitat

    calc = filtered_by_both * area_map

    result_filename, _ = species_info.filenames(output_directory_path)
    with alive_bar(manual=True) as bar:
        aoh_total = calc.to_geotiff(result_filename, and_sum=True, callback=bar)

    species_info.update_manifest({
        'range_total': range_total,
        'hab_total': hab_only_total,
        'dem_total': dem_only_total,
        'aoh_total': aoh_total,
        'prevalence': (aoh_total / range_total) if range_total else 0.0,
    })
    species_info.save_manifest(output_directory_path)


