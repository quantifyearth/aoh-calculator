# aoh-habitat-process

This command prepares habitat data for use with the **fractional method** by converting a classified habitat map into a set of per-class rasters. It splits a single habitat raster (where each pixel contains one class value) into multiple rasters with fractional coverage values, while optionally rescaling and reprojecting.

While terrestrial AOH calculations typically have one habitat class per pixel, other domains like marine environments (which represent 3D space) may have multiple  overlapping habitats. This tool enables the fractional method to work across all realms by creating the required per-class raster format.

{{ cli_help("aoh.habitat_process", prog="aoh-habitat-process") }}