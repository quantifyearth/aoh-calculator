# AOH Calculator

This repository contains code for making Area of Habitat (AOH) rasters from a mix of data sources, following the methodology described in [Brooks et al](https://www.cell.com/trends/ecology-evolution/fulltext/S0169-5347(19)30189-2) and adhearing to the IUCN Redlist Technical Working Group guidance on AoH production. This work is part of the [LIFE biodiversity map](https://www.cambridge.org/engage/coe/article-details/660e6f08418a5379b00a82b2) work at the University of Cambridge.


To generate a set of AOH rasters you will need:

* IUCN range and other metadata (habitat preference, elevation, seasonality)
* A habitat map raster
* An elevation map raster

The raster maps must be at the same scale. This code has been used with Lumbierres, Jung, and ESA datasets successfully, and using Mercator, Mollweide, and Behrmann projections.

For examples on how to run the code see the docs directory.

This project makes heavy use of [Yirgacheffe](https://github.com/quantifyearth/yirgacheffe) to do the numerical  work, and the code in this repository is mostly for getting the data to feed to yirgacheffe. The advantages of using Yirgacheffe are that it hides all the offsetting required for the math to keep the AoH logic simple, deals with the archaic GDAL API bindings, and uses map chunking to mean progress can made with minimal memory footprints despite some base map rasters being 150GB and up.


# Usage:

```SystemShell
$ python3 ./aoh-calculator/aohcalc.py
usage: aohcalc.py [-h] --habitats HABITAT_PATH --elevation-min MIN_ELEVATION_PATH --elevation-max MAX_ELEVATION_PATH [--area AREA_PATH] --crosswalk CROSSWALK_PATH --speciesdata SPECIES_DATA_PATH [--force-habitat] --output OUTPUT_PATH

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

* *habitats*: A folder containing a set of rasters, one per habitat class. Expected to be in float format, with the amount per pixel being proportional coverage for the area covered by that pixel. You can generate these from a single terrestrial habitat raster using the included `habitat_process.py`. The reason for per class rasters is to support realms with overlapping habitats, like marine.
* *elevation-min* and *elevation-max*: A pair of rasters, encoded into each pixel is the minimum and maximum elevation in the area covered by that pixel. The reason for two rasters is to support working with downsampled DEM maps for performance reasons without losing accuracy.
* *area*: An optional raster that contains the area per pixel and is just multiplied over the final AoH.
* *crosswalk*: The crosswalk table mapping from IUCN habitats to enumerated integer values found in the habitat map names.
* *speciesdata*: A geojson file containing the information about the individual species to raster.
* *force-habitat*: An optional flag that means rather than following the IUCN RLTWG guidelines, whereby if there is zero area in the habitat layer after filtering for species habitat preferneces we should revert to range, this flag will keep the result as zero. This is to allow for evaluation of scenarios that might lead to extinction via land use chnages.
* *output*: A folder where the output will be stored.

# Outputs

The results will be a series of AOH rasters, one per species per season. Alongside those results will be a [pyshark](https://github.com/quantifyearth/pyshark) provenance file encoding which data sources were used to make the outputs.