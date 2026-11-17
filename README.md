# AOH Calculator

This repository contains both a Python library and command line tools for making Area of Habitat (AOH) rasters from a mix of data sources, following the methodology described in [Brooks et al](https://www.cell.com/trends/ecology-evolution/fulltext/S0169-5347(19)30189-2) and adhering to the IUCN Redlist Technical Working Group guidance on AOH production.

## Overview

An AOH raster combines data on species range, habitat preferences and elevation preferences along with raster products such as a Digital Elevation Map (DEM) and a land cover or habitat map, and which are combined to generate a raster that refines the species range down to just those areas that match its preferences: its area of habitat, or AOH.

This package provides two implementations of the AOH method: a binary method and a fractional, or proportional, method. The binary method takes a single land cover or habitat map where each pixel is encoded to a particular land cover or habitat class (e.g., the [Copernicus Land Cover map](https://land.copernicus.eu/en/products/global-dynamic-land-cover) or the [Jung habitat map](https://zenodo.org/records/4058819)). The fractional method takes in a set of rasters, one per class, with each pixel being some proportional value. In this approach if a species has multiple habitat preferences and their maps overlap the resulting value in the AOH map will be a summation of those values.

By default the package generates a binary or fractional coverage per pixel, depending on your input layers, but if you provide the `pixel-area` option then it will covert the results into metres squared per pixel, calculating the area per pixel based on the map projection and pixel scale of the input rasters.


## Documentation

The latest version of the documentation can be found on [aoh.readthedocs.io](https://aoh.readthedocs.io/en/latest/).

