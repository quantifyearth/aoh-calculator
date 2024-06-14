import argparse
import os
from enum import Enum
from typing import List, Optional, Any, Tuple

import geopandas as gpd
import pandas as pd
from shapely.ops import transform
from pyproj import Transformer, CRS
# import pyshark # pylint: disable=W0611

import seasonality
from iucn_modlib.classes.Taxon import Taxon
from iucn_modlib.factories import TaxonFactories

from cleaning import tidy_data

class Seasonality(Enum):
    RESIDENT = "resident"
    BREEDING = "breeding"
    NONBREEDING = "nonbreeding"

    @property
    def iucn_seasons(self) -> Tuple:
        if self.value == 'resident':
            return ('Resident', 'Seasonal Occurrence Unknown')
        elif self.value == 'breeding':
            return ('Resident', 'Breeding Season', 'Seasonal Occurrence Unknown')
        elif self.value == 'nonbreeding':
            return ('Resident', 'Non-Breeding Season', 'Seasonal Occurrence Unknown')
        else:
            raise NotImplementedError(f'Unhandled seasonlity value {self.value}')


def seasonality_for_species(species: Taxon, range_file: str) -> Set[str]: 
    og_seasons = set(
        seasonality.habitatSeasonality(species) +
        seasonality.rangeSeasonality(range_file, species.taxonid)
    )
    if len(og_seasons) == 0:
        return {}
    seasons = {'resident'}
    if len(og_seasons.difference({'resident'})) > 0:
        seasons = {'breeding', 'nonbreeding'}
    return seasons


def extract_data_per_species(
    specieslist_path: str,
    speciesdata_path: str,
    iucn_data_batch: str,
    target_projection: Optional[str],
    output_directory_path: str,
) -> None:
    os.makedirs(output_directory_path, exist_ok=True)

    species_list = pd.read_csv(specieslist_path, index_col=0)
    batch = TaxonFactories.loadBatchSource(experiment['iucn_batch']) 
    species_data = gpd.read_file(speciesdata_path)

    for species_id in species_list["taxid"]:
        try:
            species = TaxonFactories.TaxonFactoryRedListBatch(species_id, batch)
        except IndexError:
            # Some of the data in the batch needs tidy...
            print(f'{species_id} not in batch')
            continue

        seasonality_list = seasonality_for_species(species, speciesdata_path)
        for seasonality in seasonality_list:
            filename = f'{seasonality}-{species.taxonid}.geojson'




    subset_of_interest = species_data[[
        "id_no",
        "seasonal",
        "elevation_lower",
        "elevation_upper",
        "full_habitat_code",
        "geometry"
    ]]


    for _, raw in subset_of_interest.iterrows():
        row = tidy_data(raw)
        if target_projection:
            transformer = Transformer.from_crs(species_data.crs, CRS(target_projection))
            new_geom = transform(transformer.transform, row.geometry)
            row.geometry = new_geom
        output_path = os.path.join(output_directory_path, f"{row.id_no}_{row.seasonal}.geojson")
        res = gpd.GeoDataFrame(row.to_frame().transpose(), crs=CRS(target_projection), geometry="geometry")
        res.to_file(output_path, driver="GeoJSON")

def main() -> None:
    parser = argparse.ArgumentParser(description="Process agregate species data to per-species-per-season for LIFE.")
    parser.add_argument(
        '--species',
        type=str,
        help='Selected list of species for evaluation',
        required=True,
        dest="species_list",
    )
    parser.add_argument(
        '--rangedata',
        type=str,
        help="Processed species range data",
        required=True,
        dest="speciesdata_path",
    )
    parser.add_argument(
        '--iucnbatch',
        type=str,
        help="IUCN download batch",
        required=True,
        dest="iucn_data_batch",
    )
    parser.add_argument(
        '--projection',
        type=str,
        help="Target projection",
        required=False,
        dest="target_projection"
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Directory where per species Geojson is stored',
        required=True,
        dest='output_directory_path',
    )
    args = parser.parse_args()

    extract_data_per_species(
        args.species_list,
        args.speciesdata_path,
        args.iucn_data_batch,
        args.target_projection,
        args.output_directory_path
    )

if __name__ == "__main__":
    main()
