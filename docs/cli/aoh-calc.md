# aoh-calc

This is the main command for calculating the AOH of a single species. It supports both binary (classified) and fractional (proportional) habitat inputs.

{{ cli_help("aoh.aohcalc", prog="aoh-calc") }}


## Usage Notes

**Habitat Input Options:**
- Use `--fractional_habitats` for a directory of per-class rasters with proportional values
- Use `--classified_habitat` for a single raster with discrete habitat class values
- You must specify exactly one of these options

**Elevation Input Options:**
- Use `--elevation` for a single DEM raster (recommended for high-resolution analyses)
- Use `--elevation-min` and `--elevation-max` together for min/max elevation pairs (for downscaled analyses)
- You must specify exactly one of these options

**Weight Layers (Optional):**
Weight layers are rasters that are multiplied with the AOH result. You can specify `--weights` multiple times to apply multiple layers, which will be multiplied together.

Common use cases:
- **Spatial masking**: Clip results to specific regions (e.g., land areas only)
  ```bash
  --weights land_mask.tif
  ```

**Output:**
Two files are created in the output directory:
- `{id_no}_{season}.tif`: The AOH raster
- `{id_no}_{season}.json`: Metadata manifest with statistics

**Other Flags:**
- `--force-habitat`: Prevents fallback to range when habitat filtering yields zero area (useful for land-use change scenarios)
- `--allow-non-iucn-habitat-codes`: By default the tool attempts to validate habitat codes as level 1 or level 2 IUCN habitat codes (e.g., "1", "1.1")

See the "Input Data Requirements" section above for detailed format specifications.
