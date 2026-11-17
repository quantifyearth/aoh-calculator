The command line tools for the AOH package are split into three sections:

### AOH

These tools are used for directly producting the AOH GeoTIFFs and preparing the input data.

- [aoh-calc](aoh-calc.md): calculates the AOH raster for a species
- [aoh-habitat-process](aoh-habitat-process.md): prepares habitat inputs

### Summaries

These commands take a set of AOH maps and generate summary statistics useful for analysing groups of species.

- [aoh-species-richness](aoh-species-richness.md): Calculate the Species Richness map based on a set of AOH rasters.
- [aoh-endemism](aoh-endemism.md): Calculate an endemism map based a set of AOH rasters.

### Validation

In [Dahal et al](https://gmd.copernicus.org/articles/15/5093/2022/) there is a method described for validating a set of AoH maps. This is implemented as validation commands, and borrows heavily from work by [Franchesca Ridley](https://www.researchgate.net/profile/Francesca-Ridley).

- [aoh-collate-data](aoh-collate-data.md): Collects all the metadata needed for validation from a set of AOH outputs.
- [aoh-fetch-gbif-data](aoh-fetch-gbif-data.md): Fetches the GBIF data required for validation.
- [aoh-validate-occurrences](aoh-validate-occurrences.md): Do occurrence validation.
- [aoh-validate-prevalence](aoh-validate-prevalence.md): Do model prevalence validation.
