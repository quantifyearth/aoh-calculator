# AoH Calculator

This repository contains code for making Area of Habitat (AoH) rasters from a mix of data sources:

* IUCN range and other metadata (habitat preference, elevation, seasonality)
* A habitat map raster
* An elevation map raster

The raster maps must be at the same scale. This code has been used with Lumbierres, Jung, and ESA datasets successfully, and using Mercator, Mollweide, and Behrmann projections.

For examples on how to run the code see the docs directory.

This project makes heavy use of [Yirgacheffe](https://github.com/quantifyearth/yirgacheffe) to do the numerical work, and the code in this repository is mostly for getting the data to feed to yirgacheffe.

# Outputs

The results will be a series of AoH rasters, one per species per season. Alongside those results will be a [pyshark](https://github.com/quantifyearth/pyshark) provenance file encoding which data sources were used to make the outputs.