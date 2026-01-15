# AOH Calculator

This repository contains both a Python library and command line tools for making Area of Habitat (AOH) rasters from a mix of data sources, following the methodology described in [Brooks et al](https://www.cell.com/trends/ecology-evolution/fulltext/S0169-5347(19)30189-2) and adhering to the IUCN Redlist Technical Working Group guidance on AOH production.

## Overview

An AOH raster combines data on species range, habitat preferences and elevation preferences along with raster products such as a Digital Elevation Map (DEM) and a land cover or habitat map, and which are combined to generate a raster that refines the species range down to just those areas that match its preferences: its area of habitat, or AOH.

This package provides two implementations of the AOH method: a binary method and a fractional, or proportional, method. The binary method takes a single land cover or habitat map where each pixel is encoded to a particular land cover or habitat class (e.g., the [Copernicus Land Cover map](https://land.copernicus.eu/en/products/global-dynamic-land-cover) or the [Jung habitat map](https://zenodo.org/records/4058819)). The fractional method takes in a set of rasters, one per class, with each pixel being some proportional value. In this approach if a species has multiple habitat preferences and their maps overlap the resulting value in the AOH map will be a summation of those values.

## Installation

The AOH Calculator is available as a Python package and can be installed via pip:

```bash
pip install aoh
```

This provides both command-line tools and a Python library for programmatic use.

For validation tools that require R, install with the validation extra:

```bash
pip install aoh[validation]
```

You will also need to following R packages installed: lme4, lmerTest, broom.mixed, emmeans, report, sklearn

### Prerequisites

You'll need GDAL installed on your system. The Python GDAL package version should match your system GDAL version. You can check your GDAL version with:

```bash
gdalinfo --version
```

Then install the matching Python package:

```bash
pip install gdal[numpy]==YOUR_VERSION_HERE
```

## Input Data Requirements

To generate AOH rasters, you will need the following inputs:

### Species Data

A GeoJSON file containing species range and attributes. Each file should include:

- **id_no**: IUCN taxon ID of the species
- **season**: Season using IUCN codes (1 = resident, 2 = breeding, 3 = non-breeding, 4 = passage, 5 = unknown)
- **elevation_lower**: Lower elevation bound (in meters) where species is found
- **elevation_upper**: Upper elevation bound (in meters) where species is found
- **full_habitat_code**: Pipe-separated list of IUCN habitat codes (e.g., "1.5|1.6|2.1")
- **geometry**: Polygon or MultiPolygon describing the species' geographic range for this season

### Habitat Data

**For binary/classified method:**
- A single GeoTIFF raster where each pixel contains an integer value representing a habitat or land cover class
- Examples: Copernicus Global Land Cover, Jung habitat classification

**For fractional/proportional method:**
- A directory containing multiple GeoTIFF rasters, one per habitat class
- Files must be named `lcc_{value}.tif` where `{value}` matches the crosswalk table
- Each pixel contains a fractional value (typically 0.0-1.0) indicating proportional coverage
- **Note**: Use the `aoh-habitat-process` tool (described below) to convert a classified habitat map into this format while optionally reprojecting and rescaling

### Elevation Data

**Single DEM (recommended for high-resolution analyses):**
- A GeoTIFF containing elevation values in meters

**Min/Max DEM pair (for downscaled analyses):**
- Two GeoTIFFs containing minimum and maximum elevation per pixel in meters
- Useful when working at coarser resolution while maintaining elevation accuracy

### Crosswalk Table

A CSV file mapping IUCN habitat codes to raster values with two columns:
- **code**: IUCN habitat code (e.g., "1.5", "2.1")
- **value**: Corresponding integer value in the land cover or habitat raster(s)

### Optional: Weight Layers

GeoTIFF rasters for area correction or masking:
- **Pixel area raster**: Converts pixel values to actual area (essential for geographic coordinate systems like WGS84)
- **Mask raster**: Binary raster to clip results to specific regions (e.g., land areas only)

### Technical Requirements

- All rasters must share the same projection and pixel resolution
- Elevation units must match between species data and DEM
- This code has been tested with Lumbierres, Jung, and ESA datasets
- Tested projections: Mercator, Mollweide, and Behrmann

## Usage

### Python Library

The AOH Calculator provides two main functions for programmatic use:

```python
from aoh import aohcalc_binary, aohcalc_fractional

# Binary method - for classified habitat maps
aohcalc_binary(
    habitat_path="landcover.tif",
    elevation_path="dem.tif",  # or tuple of (min_dem, max_dem)
    crosswalk_path="iucn_to_landcover.csv",
    species_data_path="species_123.geojson",
    output_directory_path="results/",
    weight_layer_paths=["pixel_areas.tif"],  # optional
    force_habitat=False  # optional
)

# Fractional method - for proportional habitat coverage
aohcalc_fractional(
    habitats_directory_path="fractional_habitats/",
    elevation_path=("dem_min.tif", "dem_max.tif"),  # or single DEM
    crosswalk_path="iucn_to_habitat.csv",
    species_data_path="species_123.geojson",
    output_directory_path="results/",
    weight_layer_paths=["pixel_areas.tif"],  # optional
    force_habitat=False  # optional
)

# Other utilities
from aoh import tidy_data
from aoh.summaries import species_richness
from aoh.validation import collate_data
```

Both functions create two output files:
- `{id_no}_{season}.tif`: The AOH raster
- `{id_no}_{season}.json`: Metadata including range_total, hab_total, dem_total, aoh_total, and prevalence

For detailed examples, see the doc strings on the functions directory.

# Command Line Tools

## aoh-calc

This is the main command for calculating the AOH of a single species. It supports both binary (classified) and fractional (proportional) habitat inputs.

```bash
$ aoh-calc --help
usage: aoh-calc [-h] [--fractional_habitats FRACTIONAL_HABITAT_PATH | --classified_habitat DISCRETE_HABITAT_PATH]
                [--elevation ELEVATION_PATH | --elevation-min MIN_ELEVATION_PATH --elevation-max MAX_ELEVATION_PATH]
                [--weights WEIGHT_PATHS] --crosswalk CROSSWALK_PATH
                --speciesdata SPECIES_DATA_PATH [--force-habitat]
                --output OUTPUT_PATH

Area of habitat calculator.

options:
  -h, --help            show this help message and exit
  --fractional_habitats FRACTIONAL_HABITAT_PATH
                        Directory of fractional habitat rasters, one per habitat class.
  --classified_habitat DISCRETE_HABITAT_PATH
                        Habitat raster, with each class a discrete value per pixel.
  --elevation ELEVATION_PATH
                        Elevation raster (for high-resolution analyses).
  --elevation-min MIN_ELEVATION_PATH
                        Minimum elevation raster (for downscaled analyses).
  --elevation-max MAX_ELEVATION_PATH
                        Maximum elevation raster (for downscaled analyses).
  --weights WEIGHT_PATHS
                        Optional weight layer raster(s) to multiply with result.
                        Can specify multiple times. Common uses: pixel area
                        correction, spatial masking.
  --crosswalk CROSSWALK_PATH
                        Path of habitat crosswalk table.
  --speciesdata SPECIES_DATA_PATH
                        Single species/seasonality geojson.
  --force-habitat       If set, don't treat an empty habitat layer as per IUCN RLTWG.
  --output OUTPUT_PATH  Directory where area geotiffs should be stored.
```

### Usage Notes

**Habitat Input Options:**
- Use `--fractional_habitats` for a directory of per-class rasters with proportional values
- Use `--classified_habitat` for a single raster with discrete habitat class values
- You must specify exactly one of these options

**Elevation Input Options:**
- Use `--elevation` for a single DEM raster (recommended for high-resolution analyses)
- Use `--elevation-min` and `--elevation-max` together for min/max elevation pairs (for downscaled analyses)
- You must specify exactly one of these options

**Weight Layers (Optional):**
Weight layers are rasters that are multiplied with the AOH result. You can specify `--weights` multiple times to apply multiple layers, which will be multiplied together.

Common use cases:
- **Pixel area correction**: Essential for geographic coordinate systems (WGS84) to convert pixel counts to actual area
  ```bash
  --weights pixel_areas.tif
  ```
- **Spatial masking**: Clip results to specific regions (e.g., land areas only)
  ```bash
  --weights land_mask.tif
  ```
- **Combined**: Apply both area correction and masking
  ```bash
  --weights pixel_areas.tif --weights land_mask.tif
  ```

**Output:**
Two files are created in the output directory:
- `{id_no}_{season}.tif`: The AOH raster
- `{id_no}_{season}.json`: Metadata manifest with statistics

**Other Flags:**
- `--force-habitat`: Prevents fallback to range when habitat filtering yields zero area (useful for land-use change scenarios)

See the "Input Data Requirements" section above for detailed format specifications.

## aoh-habitat-process

This command prepares habitat data for use with the **fractional method** by converting a classified habitat map into a set of per-class rasters. It splits a single habitat raster (where each pixel contains one class value) into multiple rasters with fractional coverage values, while optionally rescaling and reprojecting.

While terrestrial AOH calculations typically have one habitat class per pixel, other domains like marine environments (which represent 3D space) may have multiple overlapping habitats. This tool enables the fractional method to work across all realms by creating the required per-class raster format.

```bash
$ aoh-habitat-process --help
usage: aoh-habitat-process [-h] --habitat HABITAT_PATH --scale PIXEL_SCALE
                           [--projection TARGET_PROJECTION]
                           --output OUTPUT_PATH [-j PROCESSES_COUNT]

Downsample habitat map to raster per terrain type.

options:
  -h, --help            show this help message and exit
  --habitat HABITAT_PATH
                        Path of initial combined habitat map.
  --scale PIXEL_SCALE   Optional output pixel scale value, otherwise same as
                        source.
  --projection TARGET_PROJECTION
                        Optional target projection, otherwise same as source.
  --output OUTPUT_PATH  Destination folder for raster files.
  -j PROCESSES_COUNT    Optional number of concurrent threads to use.
```

# Summary Tools

These commands take a set of AOH maps and generate summary statistics useful for analysing groups of species.

## aoh-species-richness

The species richness map is just an indicator of how many species exist in a given area. It takes each AOH map, converts it to a boolean layer to indicate presence, and then sums the resulting boolean raster layers to give you a count in each pixel of how many species are there.

```bash
$ aoh-species-richness --help
usage: aoh-species-richness [-h] --aohs_folder AOHS --output OUTPUT
                            [-j PROCESSES_COUNT]

Calculate species richness

options:
  -h, --help          show this help message and exit
  --aohs_folder AOHS  Folder containing set of AoHs
  --output OUTPUT     Destination GeoTIFF file for results.
  -j PROCESSES_COUNT  Number of concurrent threads to use.
```

## aoh-endemism

Endemism is an indicator of how much an area of land contributes to a species overall habitat: for a species with a small area of habitat then each pixel is more precious to it than it is for a species with a vast area over which they can be found. The endemism map takes the set of AoHs and the species richness map to generate, and for each species works out the proportion of its AoH is within a given pixel, and calculates the geometric mean per pixel across all species in that pixel.

```bash
$ aoh-endemism --help
usage: aoh-endemism [-h] --aohs_folder AOHS
                    --species_richness SPECIES_RICHNESS --output OUTPUT
                    [-j PROCESSES_COUNT]

Calculate species richness

options:
  -h, --help            show this help message and exit
  --aohs_folder AOHS    Folder containing set of AoHs
  --species_richness SPECIES_RICHNESS
                        GeoTIFF containing species richness
  --output OUTPUT       Destination GeoTIFF file for results.
  -j PROCESSES_COUNT    Number of concurrent threads to use.
```

# Validation Tools

In [Dahal et al](https://gmd.copernicus.org/articles/15/5093/2022/) there is a method described for validating a set of AoH maps. This is implemented as validation commands, and borrows heavily from work by [Franchesca Ridley](https://www.researchgate.net/profile/Francesca-Ridley).

## aoh-collate-data

Before running validation, the metadata provided for each AoH map must be collated into a single table using this command:

```bash
$ aoh-collate-data --help
usage: aoh-collate-data [-h] --aoh_results AOHS_PATH --output OUTPUT_PATH

Collate metadata from AoH build.

options:
  -h, --help            show this help message and exit
  --aoh_results AOHS_PATH
                        Path of all the AoH outputs.
  --output OUTPUT_PATH  Destination for collated CSV.
```

## aoh-validate-prevalence

To run the model validation use this command:

```bash
$ aoh-validate-prevalence --help
usage: aoh-validate-prevalence [-h] --collated_aoh_data COLLATED_DATA_PATH
                               --output OUTPUT_PATH

Validate map prevalence.

options:
  -h, --help            show this help message and exit
  --collated_aoh_data COLLATED_DATA_PATH
                        CSV containing collated AoH data
  --output OUTPUT_PATH  CSV of outliers.
```

This will produce a CSV file listing just the AoH maps that fail model validation.

**Note:** The validation tools require R to be installed on your system with the `lme4` and `lmerTest` packages.

## aoh-fetch-gbif-data

This command fetches occurrence data from [GBIF](https://gbif.org) to do occurrence checking as per Dahal et al.

```bash
$ aoh-fetch-gbif-data --help
usage: aoh-fetch-gbif-data [-h] --collated_aoh_data COLLATED_DATA_PATH [--gbif_username GBIF_USERNAME] [--gbif_email GBIF_EMAIL] [--gbif_password GBIF_PASSWORD] --taxa TAXA --output_dir OUTPUT_DIR_PATH

Fetch GBIF records for species for validation.

options:
  -h, --help            show this help message and exit
  --collated_aoh_data COLLATED_DATA_PATH
                        CSV containing collated AoH data
  --gbif_username GBIF_USERNAME
                        Username of user's GBIF account. Can also be set in environment.
  --gbif_email GBIF_EMAIL
                        E-mail of user's GBIF account. Can also be set in environment.
  --gbif_password GBIF_PASSWORD
                        Password of user's GBIF account. Can also be set in environment.
  --taxa TAXA
  --output_dir OUTPUT_DIR_PATH
                        Destination directory for GBIF data.

Environment Variables:
    GBIF_USERNAME   Username of user's GBIF account.
    GBIF_EMAIL      E-mail of user's GBIF account.
    GBIF_PASSWORD   Password of user's GBIF account.
```

Important notes:

1. You will need a GBIF account for this.
2. This can take a long time, particularly for birds as there are so many records.
3. It can also generate a lot of data, hundreds of gigabytes worth, so ensure you have enough storage space!

## aoh-validate-occurrences

This command will run occurrence validation using the GBIF data fetched with the previous command.

```bash
aoh-validate-occurences --help
usage: aoh-validate-occurences [-h] --gbif_data_path GBIF_DATA_PATH --species_data SPECIES_DATA_PATH --aoh_results AOHS_PATH --output OUTPUT_PATH [-j PROCESSES_COUNT]

Validate occurrence prevelance.

options:
  -h, --help            show this help message and exit
  --gbif_data_path GBIF_DATA_PATH
                        Data containing downloaded GBIF data.
  --species_data SPECIES_DATA_PATH
                        Path of all the species range data.
  --aoh_results AOHS_PATH
                        Path of all the AoH outputs.
  --output OUTPUT_PATH  CSV of outliers.
  -j PROCESSES_COUNT    Optional number of concurrent threads to use.
```

