# AOH Calculator

This repository contains code for making Area of Habitat (AOH) rasters from a mix of data sources, following the methodology described in [Brooks et al](<https://www.cell.com/trends/ecology-evolution/fulltext/S0169-5347(19)30189-2>). This work is part of the [LIFE biodiversity map](https://www.cambridge.org/engage/coe/article-details/660e6f08418a5379b00a82b2) work at the University of Cambridge; the remainder of the analysis pipeline will be open sourced once the full paper has been accepted for publication, but given the importance of AoH calculations for many different analyses, we've opened this section early to allow others to re-use our efforts rather than spend time on yet another AoH implementation.

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
                  --output_directory OUTPUT_PATH

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
  --output_directory OUTPUT_PATH
                        Directory where area geotiffs should be stored

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
- Area: An optiona raster containing the area of each pixel, which will be multipled with the AoH raster before saving to produce a result in area rahter than pixel occupancy.
- Output directory - Two files will be output to this directory: an AoH raster with the format `{id_no}_{seasonal}.tif` and a manifest containing information about the raster `{id_no}_{seasonal}.json`.

## habitat_process.py

Whilst for terrestrial AOH calculations there is normally just one habitat class per pixel, for other realms like marine (which is a 3D space) this isn't the case, and so for these realms there is a requirement . To allow this code to work for all realms, we must split out terrestrial habitat maps that combine all classes into a single raster. To assist with this, we provide the `habitat_process.py` script, which also allows for rescaling and reprojecting.

```SystemShell
python3 ./habitat_process.py -h
usage: habitat_process.py [-h] --habitat HABITAT_PATH
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
