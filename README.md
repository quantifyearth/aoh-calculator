# AOH Calculator

This repository contains code for making Area of Habitat (AOH) rasters from a mix of data sources, following the methodology described in [Brooks et al](https://www.cell.com/trends/ecology-evolution/fulltext/S0169-5347(19)30189-2). This work is part of the [LIFE biodiversity map](https://www.cambridge.org/engage/coe/article-details/660e6f08418a5379b00a82b2) work at the University of Cambridge; the remainder of the analysis pipeline will be open sourced once the full paper has been accepted for publication, but given the importance of AoH calculations for many different analyses, we've opened this section early to allow others to re-use our efforts rather than spend time on yet another AoH implementation.

To generate a set of AOH rasters you will need:

* IUCN range and other metadata (habitat preference, elevation, seasonality)
* A habitat map raster
* An elevation map raster

The raster maps must be at the same scale. This code has been used with Lumbierres, Jung, and ESA datasets successfully, and using Mercator, Mollweide, and Behrmann projections.

For examples on how to run the code see the docs directory.

This project makes heavy use of [Yirgacheffe](https://github.com/quantifyearth/yirgacheffe) to do the numerical  work, and the code in this repository is mostly for getting the data to feed to yirgacheffe. The advantages of using Yirgacheffe are that it hides all the offsetting required for the math to keep the AoH logic simple, deals with the archaic GDAL API bindings, and uses map chunking to mean progress can made with minimal memory footprints despite some base map rasters being 150GB and up.

# Outputs

The results will be a series of AOH rasters, one per species per season. Alongside those results will be a [pyshark](https://github.com/quantifyearth/pyshark) provenance file encoding which data sources were used to make the outputs.