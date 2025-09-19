# AOH Calculator

This repository contains code for making Area of Habitat (AOH) rasters from a mix of data sources, following the methodology described in [Brooks et al](https://www.cell.com/trends/ecology-evolution/fulltext/S0169-5347(19)30189-2) and adhearing to the IUCN Redlist Technical Working Group guidance on AoH production. This work is part of the [LIFE biodiversity map](https://www.cambridge.org/engage/coe/article-details/660e6f08418a5379b00a82b2) work at the University of Cambridge. It also contains some scripts for summarising AOH data into maps of species richness and species endemism.

To generate a set of AOH rasters you will need:

- IUCN range and other metadata (habitat preference, elevation, seasonality)
- A habitat map raster
- An elevation map raster

The raster maps must be at the same scale. This code has been used with Lumbierres, Jung, and ESA datasets successfully, and using Mercator, Mollweide, and Behrmann projections.

For examples on how to run the code see the docs directory.

This project makes heavy use of [Yirgacheffe](https://github.com/quantifyearth/yirgacheffe) to do the numerical work, and the code in this repository is mostly for getting the data to feed to yirgacheffe. The advantages of using Yirgacheffe are that it hides all the offsetting required for the math to keep the AoH logic simple, deals with the archaic GDAL API bindings, and uses map chunking to mean progress can made with minimal memory footprints despite some base map rasters being 150GB and up.

# Scripts

## aohcalc.py

This is the main script designed to calculate the AOH of a single species.

```SystemShell
$ python3 ./aohcalc.py -h
usage: aohcalc.py [-h] --habitats HABITAT_PATH
                  --elevation-min MIN_ELEVATION_PATH
                  --elevation-max MAX_ELEVATION_PATH
                  [--area AREA_PATH]
                  --crosswalk CROSSWALK_PATH
                  --speciesdata SPECIES_DATA_PATH
                  [--force-habitat]
                  --output_directory OUTPUT_PATH

Area of habitat calculator.

options:
  -h, --help            show this help message and exit
  --habitats HABITAT_PATH
                        set of habitat rasters
  --elevation-min MIN_ELEVATION_PATH
                        min elevation raster
  --elevation-max MAX_ELEVATION_PATH
                        max elevation raster
  --area AREA_PATH      optional area per pixel raster. Can be 1xheight.
  --crosswalk CROSSWALK_PATH
                        habitat crosswalk table path
  --speciesdata SPECIES_DATA_PATH
                        Single species/seasonality geojson
  --force-habitat       If set, don't treat an empty habitat layer layer as per IRTWG.
  --output OUTPUT_PATH  directory where area geotiffs should be stored

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

## habitat_process.py

Whilst for terrestrial AOH calculations there is normally just one habitat class per pixel, for other realms like marine (which is a 3D space) this isn't the case, and so for these realms there is a requirement . To allow this code to work for all realms, we must split out terrestrial habitat maps that combine all classes into a single raster. To assist with this, we provide the `habitat_process.py` script, which also allows for rescaling and reprojecting.

```SystemShell
$ python3 ./habitat_process.py -h
usage: habitat_process.py [-h]
                          --habitat HABITAT_PATH
                          --output OUTPUT_PATH
                          --scale PIXEL_SCALE
                          [--projection TARGET_PROJECTION]
                          [-j PROCESSES_COUNT]

Downsample habitat map to raster per terrain type.

options:
  -h, --help            show this help message and exit
  --habitat HABITAT_PATH
                        Path of initial combined habitat map.
  --output OUTPUT_PATH  Destination folder for raster files.
  --scale PIXEL_SCALE   Optional output pixel scale value, otherwise same as source.
  --projection TARGET_PROJECTION
                        Optional target projection, otherwise same as source.
  -j PROCESSES_COUNT    Optional number of concurrent threads to use.
```

# Summaries

In the `summaries` directory you will find two scripts for taking a set of AOH maps and generating a single summary that can be useful for inferring things about a group of maps.

## Species richness

The species richness map is just an indicator of how many species exist in a given area. It takes each AOH map, converts it to a boolean layer to indicate precense, and then sums the resulting boolean raster layers to give you a count in each pixel of how many species are there.

```SystemShell
$ python3 ./summaries/species_richness.py -h
usage: species_richness.py [-h]
                           --aohs_folder AOHS
                           --output OUTPUT
                           [-j PROCESSES_COUNT]

Calculate species richness

options:
  -h, --help          show this help message and exit
  --aohs_folder AOHS  Folder containing set of AoHs
  --output OUTPUT     Destination GeoTIFF file for results.
  -j PROCESSES_COUNT  Number of concurrent threads to use.
```

## Endemism

Endemism is an indicator of how much and area of land contributes to a species overall habitat: for a species with a small area of habitat then each pixel is more precious to it than it is for a species with a vast area over which they can be found. The endemism map takes the set of AoHs and the species richness map to generate, and for each species works out the proportion of its AoH is within a given pixel, and the calculates the geometric mean per pixel across all species in that pixel.

```SystemShell
$ python3 ./summaries/endemism.py -h
usage: endemism.py [-h]
                   --aohs_folder AOHS
                   --species_richness SPECIES_RICHNESS
                   --output OUTPUT
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

# Validation

In [Dahal et al](https://gmd.copernicus.org/articles/15/5093/2022/) there is a method described for validating a set of AoH maps. This is implemented in the validation directory, and borrows heavily from work by [Franchesca Ridley](https://www.researchgate.net/profile/Francesca-Ridley).

Before running validation, the metadata provided for each AoH map must be collated into a single table using the following script:

```SystemShell
$ python3 ./validation/collate_data.py -h
usage: collate_data.py [-h] --aoh_results AOHS_PATH --output OUTPUT_PATH

Collate metadata from AoH build.

options:
  -h, --help            show this help message and exit
  --aoh_results AOHS_PATH
                        Path to directory of all the AoH outputs.
  --output OUTPUT_PATH  Destination for collated CSV.
```

## Model validation

To run the model validation use the following script:

```SystemShell
$ python3 ./validation/validate_map_prevalence.py  -h
usage: validate_map_prevalence.py [-h] --collated_aoh_data COLLATED_DATA_PATH --output OUTPUT_PATH

Validate map prevalence.

options:
  -h, --help            show this help message and exit
  --collated_aoh_data COLLATED_DATA_PATH
                        CSV containing collated AoH data
  --output OUTPUT_PATH  CSV of outliers.
```

This will produce a CSV file listing just the AoH maps that fail model validation.
