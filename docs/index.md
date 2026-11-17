# AOH Calculator

This repository contains both a Python library and command line tools for making Area of Habitat (AOH) rasters from a mix of data sources, following the methodology described in [Brooks et al](https://www.cell.com/trends/ecology-evolution/fulltext/S0169-5347(19)30189-2) and adhering to the IUCN Redlist Technical Working Group guidance on AOH production.

## Overview

An AOH raster combines data on species range, habitat preferences and elevation preferences along with raster products such as a Digital Elevation Map (DEM) and a land cover or habitat map, and which are combined to generate a raster that refines the species range down to just those areas that match its preferences: its area of habitat, or AOH.

This package provides two implementations of the AOH method: a binary method and a fractional, or proportional, method. The binary method takes a single land cover or habitat map where each pixel is encoded to a particular land cover or habitat class (e.g., the [Copernicus Land Cover map](https://land.copernicus.eu/en/products/global-dynamic-land-cover) or the [Jung habitat map](https://zenodo.org/records/4058819)). The fractional method takes in a set of rasters, one per class, with each pixel being some proportional value. In this approach if a species has multiple habitat preferences and their maps overlap the resulting value in the AOH map will be a summation of those values.

By default the package generates a binary or fractional coverage per pixel, depending on your input layers, but if you provide the `pixel-area` option then it will covert the results into metres squared per pixel, calculating the area per pixel based on the map projection and pixel scale of the other rasters.

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
    force_habitat=False,  # optional
    multiply_by_area_per_pixel=False,  # optional
    allow_non_iucn_habitat_codes=False,  # optional
)

# Fractional method - for proportional habitat coverage
aohcalc_fractional(
    habitats_directory_path="fractional_habitats/",
    elevation_path=("dem_min.tif", "dem_max.tif"),  # or single DEM
    crosswalk_path="iucn_to_habitat.csv",
    species_data_path="species_123.geojson",
    output_directory_path="results/",
    weight_layer_paths=["pixel_areas.tif"],  # optional
    force_habitat=False,  # optional
    multiply_by_area_per_pixel=False,  # optional
    allow_non_iucn_habitat_codes=False,  # optional
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
