# Input Data Requirements

To generate AOH rasters, you will need the following inputs.

## Species Data

A GeoJSON or GPKG file containing species range and attributes. Each file should include one or more entries with the following data:

- **id_no**: IUCN taxon ID of the species
- **season**: Season using IUCN codes (1 = resident, 2 = breeding, 3 = non-breeding, 4 = passage, 5 = unknown)
- **elevation_lower**: Lower elevation bound (in meters) where species is found
- **elevation_upper**: Upper elevation bound (in meters) where species is found
- **full_habitat_code**: A list of habitat codes (e.g., "1.5|1.6|2.1")
- **geometry**: Polygon or MultiPolygon describing the species' geographic range for this season

The `full_habtat_codes` field can be either a set of pipe-separated labels, or if you're using GeoJSON it can be a JSON list of strings. However, note that whilst the GeoJSON spec allows for this, many tools like QGIS and GDAL do not.

By default the habitat codes are assumed to be IUCN level 1 and level 2 habitat codes, and an error will be raised if they are not of that form. You can disable this check with either a command line argument or library call parameter depending on which way you are using the calculator.

## Habitat Data

**For binary/classified method:**
- A single GeoTIFF raster where each pixel contains an integer value representing a habitat or land cover class
- Examples: Copernicus Global Land Cover, Jung habitat classification

**For fractional/proportional method:**
- A directory containing multiple GeoTIFF rasters, one per habitat class
- Files must be named `lcc_{value}.tif` where `{value}` matches the crosswalk table
- Each pixel contains a fractional value (typically 0.0-1.0) indicating proportional coverage
- **Note**: Use the [aoh-habitat-process](cli/aoh-habitat-process.md) tool to convert a classified habitat map into this format while optionally reprojecting and rescaling

## Elevation Data

**Single DEM (recommended for high-resolution analyses):**
- A GeoTIFF containing elevation values in meters

**Min/Max DEM pair (for downscaled analyses):**
- Two GeoTIFFs containing minimum and maximum elevation per pixel in meters
- Useful when working at coarser resolution while maintaining elevation accuracy

## Crosswalk Table

A CSV file mapping habitat codes to raster values with two columns:
- **code**: Habitat code (e.g., "1.5", "2.1")
- **value**: Corresponding integer value in the land cover or habitat raster(s)

## Optional: Weight Layers

GeoTIFF rasters for scaling or masking:
- **Mask raster**: Binary raster to clip results to specific regions (e.g., land areas only)
- **Custom pixel area raster**: There is a built in feature to scale by geometric area per pixel, but if that does not suit your needs you can use your own area-per-pixel raster here.

## Technical Requirements

- All rasters must share the same projection and pixel resolution
- Elevation units must match between species data and DEM
- This code has been tested with Lumbierres et al, Jung et al, and ESA datasets
- Tested projections: Mercator, Mollweide, and Behrmann
