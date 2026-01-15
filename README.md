# AOH Calculator

This repository contains code for making Area of Habitat (AOH) rasters from a mix of data sources, following the methodology described in [Brooks et al](https://www.cell.com/trends/ecology-evolution/fulltext/S0169-5347(19)30189-2) and adhering to the IUCN Redlist Technical Working Group guidance on AoH production. This work is part of the [LIFE biodiversity map](https://www.cambridge.org/engage/coe/article-details/660e6f08418a5379b00a82b2) work at the University of Cambridge. It also contains some scripts for summarising AOH data into maps of species richness and species endemism.

## Overview

An AOH raster combines data on species range, habitat preferences and elevation preferences along with raster produces such as a Digital Elevation Map (DEM) and a land cover or habitat map and uses this information to generate a raster that regines the species range down to just those areas that match its preferences: its area of habitat.

The AOH library provides two implementations of the AOH method: a binary method and a fractional or proportional method. The binary method takes a single land cover or habitat map where each pixel is encoded to a particular land cover or habitat class (e.g., the [Copernicus Land Cover map]((https://land.copernicus.eu/en/products/global-dynamic-land-cover)) or the [Jung habitat map](https://zenodo.org/records/4058819)). The fractional method takes in a set of rasters, one per class, with each pixel being some proportional value. In this approach if a species has multiple habitat preferences and their maps overlap the resulting value in the AOH map will be a summation of those values.

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

### Library Usage

You can also use AOH Calculator as a Python library:

```python
import aoh
from aoh import tidy_data
from aoh.summaries import species_richness
from aoh.validation import collate_data

# Use core functions programmatically
# See function documentation for parameters
```

To generate a set of AOH rasters you will need:

- IUCN range and other metadata (habitat preference, elevation, seasonality)
- A habitat map raster
- An elevation map raster

The raster maps must be at the same scale. This code has been used with Lumbierres, Jung, and ESA datasets successfully, and using Mercator, Mollweide, and Behrmann projections.

For examples on how to run the code see the docs directory.

# Command Line Tools

## aoh-calc

This is the main command designed to calculate the AOH of a single species.

```bash
$ aoh-calc --help
usage: aoh-calc [-h] --habitats HABITAT_PATH
                --elevation-min MIN_ELEVATION_PATH
                --elevation-max MAX_ELEVATION_PATH [--area AREA_PATH]
                --crosswalk CROSSWALK_PATH --speciesdata SPECIES_DATA_PATH
                [--force-habitat] --output OUTPUT_PATH

Area of habitat calculator.

options:
  -h, --help            show this help message and exit
  --habitats HABITAT_PATH
                        Directory of habitat rasters, one per habitat class.
  --elevation-min MIN_ELEVATION_PATH
                        Minimum elevation raster.
  --elevation-max MAX_ELEVATION_PATH
                        Maximum elevation raster
  --area AREA_PATH      Optional area per pixel raster. Can be 1xheight.
  --crosswalk CROSSWALK_PATH
                        Path of habitat crosswalk table.
  --speciesdata SPECIES_DATA_PATH
                        Single species/seasonality geojson.
  --force-habitat       If set, don't treat an empty habitat layer layer as
                        per IRTWG.
  --output OUTPUT_PATH  Directory where area geotiffs should be stored.
```

To calculate the AoH we need the following information:

- Species data: A GeoJSON file that contains at least the following values about the species in question:
  - id_no: the IUCN taxon ID of the species
  - seasonal: the season using IUCN codes (1 = resident, 2 = breeding, 3 = non-breeding, 4 = passage, 5 = unknown)
  - elevation_upper: The upper bound of elevation in which species is found
  - elevation_lower: The lower bound of elevation in which species is found
  - full_habitat_code: A list of the IUCN habitat codes in which the species is found
  - geometry: A polygon or multipolygon describing the range of the species in that season
- Habitats: A directory containing a series of GeoTIFFs, one per habitat class, indicating which pixels contain that habitat. Float values indicate partial occupancy.
- Elevation-max/Elevation-min: Two GeoTIFFs, in which the highest and lowest elevation for that pixel is recorded. Must be in same units as those in the GeoJSON.
- Crosswalk: A crosswalk table in CSV format that converts between the IUCN habitat classes and names of the habitat raster layers.
- Area: An optiona raster containing the area of each pixel, which will be multipled with the AoH raster before saving to produce a result in area rather than pixel occupancy.
- Force habitat: An optional flag that means rather than following the IUCN RLTWG guidelines, whereby if there is zero area in the habitat layer after filtering for species habitat preferneces we should revert to range, this flag will keep the result as zero. This is to allow for evaluation of scenarios that might lead to extinction via land use chnages.
- Output directory - Two files will be output to this directory: an AoH raster with the format `{id_no}_{seasonal}.tif` and a manifest containing information about the raster `{id_no}_{seasonal}.json`.

## aoh-habitat-process

Whilst for terrestrial AOH calculations there is normally just one habitat class per pixel, for other realms like marine (which is a 3D space) this isn't necessarily the case. To allow this package to work for all realms, we must split out terrestrial habitat maps that combine all classes into a single raster into per layer rasters. To assist with this, we provide the `aoh-habitat-process` command, which also allows for rescaling and reprojecting.

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

