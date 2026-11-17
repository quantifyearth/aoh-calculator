# aoh-endemism

Endemism is an indicator of how much an area of land contributes to a species overall habitat: for a species with a small area of habitat then each pixel is more precious to it than it is for a species with a vast area over which they can be found. The endemism map takes the set of AoHs and the species richness map to generate, and for each species works out the proportion of its AoH is within a given pixel, and calculates the geometric mean per pixel across all species in that pixel.

{{ cli_help("aoh.summaries.endemism", prog="aoh-endemism") }}