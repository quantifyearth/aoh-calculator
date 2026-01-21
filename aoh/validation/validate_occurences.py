import argparse
import json
import math
import os
from functools import partial
from multiprocessing import cpu_count, Pool
from pathlib import Path
from typing import NamedTuple

import geopandas as gpd
import pandas as pd
import yirgacheffe as yg
from pyproj import Transformer
from shapely.geometry import Point

class Record(NamedTuple):
    iucn_taxon_id: int
    total_records: int
    clipped_points: int
    unique_points: int
    matches: int
    point_prevalence: float | None
    model_prevalence: float
    is_valid: bool
    is_outlier: bool | None

def process_species(
    aohs_path: Path,
    species_data_path: Path,
    species_occurrences: pd.DataFrame,
) -> Record:

    if len(species_occurrences) == 0:
        raise ValueError("No occurrences")

    taxon_ids = species_occurrences.iucn_taxon_id.unique()
    if len(taxon_ids) > 1:
        raise ValueError("Too many taxon IDs")
    taxon_id = taxon_ids[0]

    aoh_files = list(aohs_path.glob(f"**/{taxon_id}_*.tif"))
    # We here are aborting on those species with no data or those
    # with multiple seasons
    if len(aoh_files) == 0:
        raise FileNotFoundError("No AOHs found")
    if len(aoh_files) > 1:
        raise NotImplementedError("Multi-season AOHs not yet supported")

    aoh_tiff_path = aoh_files[0]
    aoh_data_path = aoh_tiff_path.with_suffix(".json")
    with open(aoh_data_path, 'r', encoding='utf-8') as f:
        aoh_data = json.load(f)

    species_data_files = list(species_data_path.glob(f"**/{taxon_id}_*.geojson"))
    if len(species_data_files) != 1:
        raise RuntimeError(
            f"We expected one GeoJSON file beside the GeoTIFF, we found {len(species_data_files)} for {taxon_id}"
        )
    species_range = gpd.read_file(species_data_files[0])

    # From Dahal et al: "This ensured that we only included points which fell inside
    # the boundaries of the selected range maps."
    points_gdf = gpd.GeoDataFrame(
        species_occurrences,
        geometry=[
            Point(lon, lat)
            for lon, lat in
            zip(species_occurrences['decimalLongitude'], species_occurrences['decimalLatitude'])
        ],
        crs='EPSG:4326',
    )
    clipped_points = gpd.sjoin(points_gdf, species_range, predicate='within', how='inner')

    pixel_set = set()
    with yg.read_raster(aoh_files[0]) as aoh:
        # The GBIF data is in WGS84, and so we need to map that to a point in the
        # AOH raster projection space
        transformer = Transformer.from_crs("EPSG:4326", aoh.map_projection.name)

        results = []
        for _, row in clipped_points.iterrows():

            # Ridley et al: "The distance-weighted, average fractional coverage of AOH surrounding
            # each species point locality was determined using bilinear interpolation of the four
            # nearest cells."

            x, y = transformer.transform(row.decimalLongitude, row.decimalLatitude)
            aligned_x = (x - aoh.area.left) / aoh.map_projection.xstep
            aligned_y = (y - aoh.area.top) / aoh.map_projection.ystep
            floored_aligned_x = math.floor(aligned_x)
            floored_aligned_y = math.floor(aligned_y)
            if (aligned_x - floored_aligned_x) < 0.5:
                pixel_x = floored_aligned_x - 1
            else:
                pixel_x = floored_aligned_x
            if (aligned_y - floored_aligned_y) < 0.5:
                pixel_y = floored_aligned_y - 1
            else:
                pixel_y = floored_aligned_y

            # Dahal et al: "We also made sure that only one point locality was allowed per pixel of
            # the AOH map to avoid clustering of points."
            if (pixel_x, pixel_y) in pixel_set:
                continue
            pixel_set.add((pixel_x, pixel_y))

            rawvalues = aoh.read_array(pixel_x, pixel_y, 2, 2)

            # Technically we should do a bilinear interpolation, but given the
            # occurrence check is binary, we can just see if there's any non
            # zero pixels. If we had a threshold higher than zero, then this
            # isn't sufficient and should be replaced
            results.append(rawvalues.sum() > 0.0)

    # From Dahal et al: "Finally, we excluded species which had fewer than 10 point localities after
    # all the filters were applied."
    is_valid = len(results) >= 10

    model_prevalence = aoh_data['prevalence']
    matches = len([x for x in results if x])
    if is_valid:
        point_prevalence = matches / len(results)

        # From Dahal et al: "If the point prevalence exceeded model prevalence at
        # species level, the AOH maps performed better than random,
        # otherwise they were no better than random."
        #
        # However, note that this means if you have a point prevalence of 1.0 (all
        # points match) and a model prevalence of 1.0 (range and AOH match, which
        # under the IUCN method is the preferred fallback if we have zero on either
        # elevation filtering or habitat filtering), then that would still be marked
        # as an outlier, (as 1.0 is not exceeding 1.0) which seems wrong, so I'm
        # special casing that.
        is_outlier = (point_prevalence != 1.0) and (point_prevalence < model_prevalence)
    else:
        point_prevalence = None
        is_outlier = None


    return Record(
        taxon_id,                           # Species Redlist ID
        len(species_occurrences),           # Raw number of occurrences from GBIF
        len(clipped_points),                # Number of occurrences clipped to species range
        len(results),                       # Number of unique occurrences by pixel
        matches,                            # Number of occurrences within AOH
        point_prevalence,                   # Point prevalence as per Dahal et al
        model_prevalence,                   # Model prevalence as per Dahal et al
        is_valid,                           # Whether we consider the result valid
        is_outlier,                         # Whether species is considered an outlier
    )

def process_species_wrapper(
    aohs_path: Path,
    species_data_path: Path,
    species_occurrences: pd.DataFrame,
) -> Record | None:
    # This wrapper exists to make it easier to write unit tests for process species by having it thrown
    # unique exceptions for each failure, but allowing us to use pool.map to invoke it which won't
    # tolerate those.
    try:
        return process_species(aohs_path, species_data_path, species_occurrences)
    except (ValueError, FileNotFoundError, RuntimeError, NotImplementedError):
        return None

def validate_occurrences(
    gbif_data_path: Path,
    aohs_path: Path,
    species_data_path: Path,
    output_path: Path,
    process_count: int,
) -> None:
    os.makedirs(output_path.parent, exist_ok=True)

    # The input is from the points.csv generated by fetch_gbif_data.py, which has the columns:
    # iucn_taxon_id, gbif_id, decimalLatitude, decimalLongitude, assessment year
    occurrences = pd.read_csv(gbif_data_path)
    occurrences.drop(columns=['gbif_id', 'year'], inplace=True)
    occurrences.sort_values(['iucn_taxon_id', 'decimalLatitude'], inplace=True)
    occurrences_per_species = [group for _, group in occurrences.groupby('iucn_taxon_id')]
    with Pool(processes=process_count) as pool:
        results_per_species = pool.map(partial(
            process_species_wrapper,
            aohs_path,
            species_data_path
        ), occurrences_per_species)
    cleaned_results = [x for x in results_per_species if x is not None]

    summary = pd.DataFrame(cleaned_results)
    summary.to_csv(output_path, index=False)

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate occurrence prevelance.")
    parser.add_argument(
        '--gbif_data_path',
        type=Path,
        help="Data containing downloaded GBIF data.",
        required=True,
        dest="gbif_data_path"
    )
    parser.add_argument(
        '--species_data',
        type=Path,
        help="Path of all the species range data.",
        required=True,
        dest="species_data_path",
    )
    parser.add_argument(
        '--aoh_results',
        type=Path,
        help="Path of all the AoH outputs.",
        required=True,
        dest="aohs_path"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        dest="output_path",
        help="CSV of outliers."
    )
    parser.add_argument(
        "-j",
        type=int,
        required=False,
        default=cpu_count(),
        dest="processes_count",
        help="Optional number of concurrent threads to use."
    )
    args = parser.parse_args()

    validate_occurrences(
        args.gbif_data_path,
        args.aohs_path,
        args.species_data_path,
        args.output_path,
        args.processes_count,
    )

if __name__ == "__main__":
    main()
