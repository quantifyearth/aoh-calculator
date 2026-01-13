import os
from pathlib import Path

import geopandas as gpd

class SpeciesInfo:

    def __init__(species_data_path: Path)
        os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"
        filtered_species_info = gpd.read_file(species_data_path)
        if filtered_species_info.shape[0] != 1:
            raise ValueError("Expected just single species entry per GeoJSON file")

        # We drop the geometry as that's a lot of data, more than the raster often, and make
        # sure things are typed in regular Python types for later saving to JSON.
        self.species_info = filtered_species_info.drop('geometry', axis=1)
        self.manifest = {k: v[0].item() if hasattr(v[0], 'item') else v[0] for (k, v) in species_info.items()}

    @property
    def species_id(self):
        return self.species_info.id_no.values[0]



        self.species_id = filtered_species_info.id_no.values[0]
        try:
            seasonality = filtered_species_info.season.values[0]
            result_filename = output_directory_path / f"{species_id}_{seasonality}.tif"
            manifest_filename = output_directory_path / f"{species_id}_{seasonality}.json"
        except AttributeError:
            seasonality = None
            result_filename = output_directory_path / f"{species_id}.tif"
            manifest_filename = output_directory_path / f"{species_id}.json"

        try:
            self.elevation_lower = math.floor(float(filtered_species_info.elevation_lower.values[0]))
            self.elevation_upper = math.ceil(float(filtered_species_info.elevation_upper.values[0]))
            raw_habitats = set(filtered_species_info.full_habitat_code.values[0].split('|'))
        except (AttributeError, TypeError):
            logger.error("Species data missing one or more needed attributes: %s", filtered_species_info)
            self.manifest["error"] = "Species data missing one or more needed attributes"
            with open(manifest_filename, 'w', encoding="utf-8") as f:
                json.dump(manifest, f)
            return

        habitat_list = crosswalk_habitats(crosswalk_table, raw_habitats)
        if force_habitat and len(habitat_list) == 0:
            logger.error("No habitats found in crosswalk! %s_%s had %s", species_id, seasonality, raw_habitats)
            self.manifest["error"] = "No habitats found in crosswalk"
            with open(manifest_filename, 'w', encoding="utf-8") as f:
                json.dump(manifest, f)
            return

