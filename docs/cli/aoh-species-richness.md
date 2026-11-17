# aoh-species-richness

The species richness map is just an indicator of how many species exist in a given area. It takes each AOH map, converts it to a boolean layer to indicate presence, and then sums the resulting boolean raster layers to give you a count in each pixel of how many species are there.

{{ cli_help("aoh.summaries.species_richness", prog="aoh-species-richness") }}
