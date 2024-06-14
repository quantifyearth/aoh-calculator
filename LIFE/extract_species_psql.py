import argparse
import os
from typing import Optional

# import pyshark # pylint: disable=W0611
import geopandas as gpd
import pyproj
from sqlalchemy import create_engine, text

from cleaning import tidy_data

SEASON_NAME = {
    1: "RESIDENT",
    2: "BREEDING",
    3: "NONBREEDING",
}

STATEMENT = """
WITH habitat_seasons AS (
	SELECT 
        assessment_habitats.assessment_id, 
        assessment_habitats.habitat_id,
        CASE
            WHEN (assessment_habitats.supplementary_fields->>'season') ILIKE 'Resident' THEN 1
            WHEN (assessment_habitats.supplementary_fields->>'season') ILIKE 'Breeding%' THEN 2
            WHEN (assessment_habitats.supplementary_fields->>'season') ILIKE 'Non%Breed%' THEN 3
            WHEN (assessment_habitats.supplementary_fields->>'season') ILIKE 'Pass%' THEN 4
            WHEN (assessment_habitats.supplementary_fields->>'season') ILIKE '%un%n%' THEN 1 -- capture 'uncertain' and 'unknown' as resident
            ELSE 1
        END AS seasonal
    FROM 
        public.assessments
        LEFT JOIN taxons ON taxons.id = assessments.taxon_id
        LEFT JOIN assessment_habitats ON assessment_habitats.assessment_id = assessments.id
    WHERE 
        assessments.latest = 'true'
),
unique_seasons AS (
  	SELECT DISTINCT ON (taxons.scientific_name, habitat_seasons.seasonal)
        assessments.id AS assessment_id,
        assessments.sis_taxon_id as id_no,
        taxons.scientific_name,
        taxons.class_name,
        assessment_ranges.seasonal,
        assessment_ranges.presence,
        assessment_ranges.origin,
        habitat_seasons.habitat_id,
        habitat_lookup.code AS habitat_code,
        STRING_AGG(habitat_lookup.code, '|') OVER (PARTITION BY taxons.scientific_name, habitat_seasons.seasonal ORDER BY assessment_ranges.id) AS full_habitat_code,
        STRING_AGG(system_lookup.description->>'en', '|') OVER (PARTITION BY taxons.scientific_name, habitat_seasons.seasonal ORDER BY assessment_ranges.id) AS systems,
        (ST_COLLECT(assessment_ranges.geom::geometry) OVER (PARTITION BY taxons.scientific_name, habitat_seasons.seasonal ORDER BY assessment_ranges.id))::geography AS geometry,
        habitat_lookup.description,
        (assessment_supplementary_infos.supplementary_fields->>'ElevationLower.limit')::numeric AS elevation_lower,
        (assessment_supplementary_infos.supplementary_fields->>'ElevationUpper.limit')::numeric AS elevation_upper,
        ROW_NUMBER() OVER (PARTITION BY taxons.scientific_name, habitat_seasons.seasonal ORDER BY assessments.id, assessment_ranges.id) AS rn
    FROM 
        assessments
        LEFT JOIN taxons ON taxons.id = assessments.taxon_id
        LEFT JOIN assessment_ranges ON assessment_ranges.assessment_id = assessments.id
        LEFT JOIN habitat_seasons ON habitat_seasons.assessment_id = assessments.id AND habitat_seasons.seasonal = assessment_ranges.seasonal
        LEFT JOIN assessment_systems ON assessment_systems.assessment_id = assessments.id
        LEFT JOIN system_lookup ON assessment_systems.system_lookup_id = system_lookup.id
        LEFT JOIN habitat_lookup ON habitat_lookup.id = habitat_seasons.habitat_id
        LEFT JOIN assessment_supplementary_infos ON assessment_supplementary_infos.assessment_id = assessments.id
        LEFT JOIN red_list_category_lookup ON red_list_category_lookup.id = assessments.red_list_category_id
    WHERE 
        assessments.latest = 'true'
        AND taxons.class_name = 'AVES'
        AND habitat_seasons.habitat_id is not null
        AND assessment_ranges.presence IN {presence}
        AND assessment_ranges.origin IN (1, 2, 6)
        AND assessment_ranges.seasonal IN (1, 2, 3)
        AND red_list_category_lookup.code != 'EX'
    )
SELECT 
    id_no,
    seasonal,
    COALESCE(elevation_lower, -500.0) as elevation_lower,
    COALESCE(elevation_upper, 9000.0) as elevation_upper,
    full_habitat_code,
    geometry
FROM 
    unique_seasons
WHERE
    rn = 1
    -- the below queries must happen on the aggregate data
    AND full_habitat_code NOT LIKE '7%'
    AND full_habitat_code NOT LIKE '%|7%'
    AND systems NOT LIKE '%Marine%'
"""

CURRENT_STATEMENT = STATEMENT.format(presence="(1, 2)")
HISTORIC_STATEMENT = STATEMENT.format(presence="(1, 2, 4, 5)")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_CONFIG = (
	f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

def extract_data_per_species(
    output_directory_path: str,
    target_projection: Optional[str],
) -> None:

    # The geometry is in CRS 4326, but the AoH work is done in World_Behrmann, aka Projected CRS: ESRI:54017
    src_crs = pyproj.CRS.from_epsg(4326)
    target_crs = pyproj.CRS.from_string(target_projection)

    engine = create_engine(DB_CONFIG, echo=False)
    for era, statement in ("current", CURRENT_STATEMENT), ("historic", HISTORIC_STATEMENT):
        os.makedirs(os.path.join(output_directory_path, era), exist_ok=True)
        dfi = gpd.read_postgis(text(statement), con=engine, geom_col="geometry", chunksize=1024)
        for df in dfi:
            for _, raw in df.iterrows():

                row = tidy_data(raw)
                output_path = os.path.join(output_directory_path, era, f"{row.id_no}_{SEASON_NAME[row.seasonal]}.geojson")
                res = gpd.GeoDataFrame(row.to_frame().transpose(), crs=src_crs, geometry="geometry")
                res_projected = res.to_crs(target_crs)
                res_projected.to_file(output_path, driver="GeoJSON")
    

def main() -> None:
    parser = argparse.ArgumentParser(description="Process agregate species data to per-species-file.")
    parser.add_argument(
        '--output',
        type=str,
        help='Directory where per species Geojson is stored',
        required=True,
        dest='output_directory_path',
    )
    parser.add_argument(
        '--projection',
        type=str,
        help="Target projection",
        required=False,
        dest="target_projection",
        default="ESRI:54017"
    )
    args = parser.parse_args()

    extract_data_per_species(
        args.output_directory_path,
        args.target_projection
    )

if __name__ == "__main__":
    main()
