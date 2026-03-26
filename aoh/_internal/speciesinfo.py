import json
import math
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .utils import IUCNFormatFilename

def load_crosswalk_table(table_file_name: Path) -> dict[str,list[int]]:
    rawdata = pd.read_csv(table_file_name)
    result : dict[str,list[int]] = {}
    for _, row in rawdata.iterrows():
        code = str(row.code)
        try:
            result[code].append(int(row.value))
        except KeyError:
            result[code] = [int(row.value)]
    return result

def crosswalk_habitats(crosswalk_table: dict[str, list[int]], raw_habitats: set[str]) -> set[int]:
    result = set()
    for habitat in raw_habitats:
        try:
            crosswalked_habatit = crosswalk_table[habitat]
        except KeyError:
            continue
        result |= set(crosswalked_habatit)
    return result


class SpeciesInfo:

    def __init__(self, species_data_path: Path, crosswalk_path: Path) -> None:
        os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"
        filtered_species_info = gpd.read_file(species_data_path)
        if filtered_species_info.shape[0] != 1:
            raise ValueError("Expected just single species entry per GeoJSON file")

        # We drop the geometry as that's a lot of data, more than the raster often, and make
        # sure things are typed in regular Python types for later saving to JSON.
        self.species_info = filtered_species_info.drop('geometry', axis=1)
        self.manifest = {k: v[0].item() if hasattr(v[0], 'item') else v[0] for (k, v) in self.species_info.items()}

        self.crosswalk_table = load_crosswalk_table(crosswalk_path)

    @property
    def species_id(self) -> int:
        return int(self.species_info.id_no.values[0])

    @property
    def assessment_id(self) -> int | None:
        try:
            return int(self.species_info.assessment_id.values[0])
        except AttributeError:
            return None

    @property
    def season(self) -> str | None:
        try:
            return self.species_info.season.values[0]
        except AttributeError:
            return None

    @property
    def elevation_lower(self) -> int:
        try:
            return math.floor(float(self.species_info.elevation_lower.values[0]))
        except (AttributeError, TypeError) as exc:
            self.manifest["error"] = "Species data missing or corrupt elevation lower"
            raise ValueError(self.manifest["error"]) from exc

    @property
    def elevation_upper(self) -> int:
        try:
            return math.floor(float(self.species_info.elevation_upper.values[0]))
        except (AttributeError, TypeError) as exc:
            self.manifest["error"] = "Species data missing or corrupt elevation upper"
            raise ValueError(self.manifest["error"]) from exc

    @property
    def raw_habitats(self) -> set[str]:
        try:
            return set(self.species_info.full_habitat_code.values[0].split('|'))
        except (AttributeError, TypeError) as exc:
            self.manifest["error"] = "Species data missing or corrupt habitat data"
            raise ValueError(self.manifest["error"]) from exc

    def filenames(self, output_directory_path: Path) -> tuple[Path,Path]:
        raster_filename = IUCNFormatFilename("aoh", self.species_id, self.assessment_id, self.season, ".tif")
        json_filename = IUCNFormatFilename("aoh", self.species_id, self.assessment_id, self.season, ".json")
        return output_directory_path / raster_filename.to_path(), output_directory_path / json_filename.to_path()

    def save_manifest(self, output_directory_path:Path, error_message: str | None = None) -> None:
        _, manifest_filename = self.filenames(output_directory_path)
        if error_message is not None:
            self.manifest["error"] = error_message

        with open(manifest_filename, 'w', encoding="utf-8") as f:
            json.dump(self.manifest, f)

    def update_manifest(self, values: dict) -> None:
        self.manifest.update(values)

    @property
    def habitat_list(self) -> set[int]:
        return crosswalk_habitats(self.crosswalk_table, self.raw_habitats)
