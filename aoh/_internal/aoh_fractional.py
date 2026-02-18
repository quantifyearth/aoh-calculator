import logging
import operator
import os
from functools import reduce
from pathlib import Path

import yirgacheffe as yg
from alive_progress import alive_bar # type: ignore

from .speciesinfo import SpeciesInfo

logger = logging.getLogger(__name__)

yg.constants.YSTEP = 2048

def aohcalc_fractional(
    habitats_directory_path: Path | str,
    elevation_path: Path | str | tuple[Path,Path] | tuple[str,str],
    crosswalk_path: Path | str,
    species_data_path: Path | str,
    output_directory_path: Path | str,
    weight_layer_paths: list[Path] | list[str] | None = None,
    force_habitat: bool=False,
    multiply_by_area_per_pixel: bool=False,
) -> None:
    """Calculate an Area of Habitat using fractional/proportional habitat data.

    This implementation of the AOH method from Brooks et al. (2019) works with
    fractional habitat coverage where each habitat class has its own raster with
    proportional values per pixel. When multiple habitat types preferred
    by a species overlap in a pixel, their corresponding values are summed and
    if necessary clipped to 1.0.

    This method is particularly useful for:
    - Sub-pixel habitat representation
    - Mixed land-use scenarios
    - Three dimensional domains such as marine habitats
    - Uncertainty quantification in habitat mapping

    The method filters a species' geographic range by:
    1. Habitat suitability (summing fractional coverage of suitable habitats)
    2. Elevation preferences (using DEM data)
    3. Optional weight layers (e.g., pixel area correction or masking)

    Elevation data is accepted in two forms. Either a single raster with a heigh
    value per pixel, or a pair of rasters, each containing the lower and upper
    limits of the elevation for that pixel. This later option is useful for
    running pipelines at a lower resolution but keeping better accuracy than
    a single elevation layer would.

    IUCN Fallback Behavior: Following IUCN Red List Technical Working Group
    recommendations, if habitat or elevation filtering results in zero area, the
    method reverts to the full species range unless force_habitat=True.

    Args:
        habitats_directory_path: Path to a directory containing fractional habitat
            rasters. Files must be named "lcc_{value}.tif" where {value} matches
            the class value in the crosswalk CSV. Each pixel should contain
            proportional coverage for the given class between 0.0 and 1.0.
        elevation_path: Either a single DEM raster path, or a tuple of
            (min_elevation_path, max_elevation_path) for downscaled analyses
            following IUCN recommendations.
        crosswalk_path: Path to a CSV file mapping IUCN habitat codes to raster
            file identifiers. Must have columns 'code' (IUCN habitat code) and
            'value' (used to construct filename lcc_{value}.tif).
        species_data_path: Path to a GeoJSON file containing species range and
            attributes. Must include: id_no, season, elevation_lower, elevation_upper,
            and full_habitat_code (pipe-separated IUCN codes).
        output_directory_path: A directory for output files. Creates two files:
            - {id_no}_{season}.tif: AOH raster (or {id_no}.tif if no season)
            - {id_no}_{season}.json: Metadata including range_total, hab_total,
              dem_total, aoh_total, and prevalence
        weight_layer_paths: An optional list of rasters to multiply with the result.
            Common uses include pixel area correction and spatial masking. Multiple
            rasters are multiplied together.
        force_habitat: If True, do not revert to range when habitat filtering
            yields zero area. Useful for land-use change scenarios where habitat
            loss should result in zero AOH.
        multiply_by_area_per_pixel: If True, for each pixel multiply its value by
            the area of that pixel in metres squared based on the map projection
            and pixel scale.

    Returns:
        None. Outputs are written to files in output_directory_path.

    Notes:
        - All rasters must share the same projection and pixel resolution
        - Output raster extent is clipped to species range geometry
        - Fractional values for multiple habitats are summed and clipped to max 1.0

    Examples:
        Basic usage with fractional habitat maps:
            >>> aohcalc_fractional(
            ...     habitats_directory_path="fractional_habitats/",
            ...     elevation_path="dem.tif",
            ...     crosswalk_path="iucn_to_habitat.csv",
            ...     species_data_path="species_123.geojson",
            ...     output_directory_path="results/"
            ... )

        With pixel area correction for WGS84:
            >>> aohcalc_fractional(
            ...     habitats_directory_path="fractional_habitats/",
            ...     elevation_path="dem.tif",
            ...     crosswalk_path="iucn_to_habitat.csv",
            ...     species_data_path="species_123.geojson",
            ...     output_directory_path="results/",
            ...     weight_layer_paths=["pixel_areas.tif"]
            ... )

        Downscaled analysis with min/max elevation:
            >>> aohcalc_fractional(
            ...     habitats_directory_path="fractional_habitats/",
            ...     elevation_path=("dem_min.tif", "dem_max.tif"),
            ...     crosswalk_path="iucn_to_habitat.csv",
            ...     species_data_path="species_123.geojson",
            ...     output_directory_path="results/"
            ... )

        Land-use change scenario (force habitat, no fallback to range):
            >>> aohcalc_fractional(
            ...     habitats_directory_path="future_scenario/",
            ...     elevation_path="dem.tif",
            ...     crosswalk_path="iucn_to_habitat.csv",
            ...     species_data_path="species_123.geojson",
            ...     output_directory_path="results/",
            ...     force_habitat=True
            ... )

    References:
        Brooks, T. M., et al. (2019). Measuring Terrestrial Area of Habitat (AOH)
        and Its Utility for the IUCN Red List. Trends in Ecology & Evolution, 34(11),
        977-986. https://doi.org/10.1016/j.tree.2019.06.009
    """

    habitat_path = Path(habitats_directory_path)
    if isinstance(elevation_path, tuple):
        if len(elevation_path) != 2:
            raise ValueError("Elevation path should be single raster or tuple of min/max raster paths.")
        elevation_path = (Path(elevation_path[0]), Path(elevation_path[1]))
    else:
        elevation_path = Path(elevation_path)
    crosswalk_path = Path(crosswalk_path)
    species_data_path = Path(species_data_path)
    if weight_layer_paths is not None:
        weight_layer_paths = [Path(x) for x in weight_layer_paths]
    output_directory_path = Path(output_directory_path)

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
        logger.error("No habitats found in crosswalk! %s_%s had %s",
            species_info.species_id, species_info.season, species_info.raw_habitats)
        species_info.save_manifest(output_directory_path, "No habitats found in crosswalk")
        return

    ideal_habitat_map_files = [habitat_path / f"lcc_{x}.tif" for x in habitat_list]
    habitat_map_files = [x for x in ideal_habitat_map_files if x.exists()]
    if force_habitat and len(habitat_map_files) == 0:
        logger.error("No matching habitat layers found for %s_%s in %s: %s",
                     species_info.species_id, species_info.season, habitat_path, habitat_list)
        species_info.save_manifest(output_directory_path, "No matching habitat layers found")
        return

    habitat_maps = [yg.read_raster(x) for x in habitat_map_files]

    if isinstance(elevation_path, Path):
        min_elevation_map = yg.read_raster(elevation_path)
        max_elevation_map = min_elevation_map
    elif isinstance(elevation_path, tuple):
        if len(elevation_path) != 2:
            raise ValueError("elevation path should be single raster or tuple of min/max raster paths.")
        min_elevation_map = yg.read_raster(elevation_path[0])
        max_elevation_map = yg.read_raster(elevation_path[1])
    else:
        raise ValueError("Elevation path should be single raster or tuple of min/max raster paths.")

    projection = min_elevation_map.map_projection
    assert projection is not None
    area_per_pixel = yg.area_raster(projection) if multiply_by_area_per_pixel else 1.0

    range_map = yg.read_shape_like(
        species_data_path,
        min_elevation_map,
        datatype=yg.DataType.Float32,
    )

    # We can treat the area_per_pixel value as a built in weight
    weights_map : float | yg.YirgacheffeLayer = area_per_pixel
    if weight_layer_paths is not None and weight_layer_paths:
        rasters = [area_per_pixel]
        for p in weight_layer_paths:
            try:
                raster = yg.read_narrow_raster(p)
            except ValueError:
                raster = yg.read_raster(p)
            rasters.append(raster)
        weights_map = reduce(operator.mul, rasters)

    range_total = (range_map * weights_map).sum()

    # We've had instances of overflow issues with large ranges in the past
    assert range_total >= 0.0

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
    else:
        filtered_by_habtitat = range_map

    # Elevation evaluation. As per the IUCN Redlist Technical Working Group recommendations, if the elevation
    # filtering of the DEM returns zero, then we ignore this layer on the assumption that there is error in the
    # elevation data. This aligns with the data hygine practices recommended by Busana et al, as implemented
    # in cleaning.py, where any bad values for elevation cause us assume the entire range is valid.
    hab_only_total = (filtered_by_habtitat * weights_map).sum()

    filtered_elevation = (min_elevation_map <= elevation_upper) & (max_elevation_map >= elevation_lower)

    dem_only_total = (filtered_elevation * range_map * weights_map).sum()

    filtered_by_both = filtered_elevation * filtered_by_habtitat
    if filtered_by_both.sum() == 0:
        filtered_by_both = filtered_by_habtitat

    calc = filtered_by_both * weights_map

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
