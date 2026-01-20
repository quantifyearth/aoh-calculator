## v2.0.1 (20/01/2026)

### Fixed

* Fixed broken import on pyproject.toml
* Habitat processing regression due to change in GDAL default behaviour.

## v2.0.0 (15/01/2026)

### Changed

* Renamed the existing AOH calculation function to make it clear that it is for fractional AOH calculations.
* Tweaked parameters to allow both single and min/max pair DEM files.
* Changed parameter order to be consistent with new binary AOH method.
* Updated aoh-calc command to allow multiple weight layers rather than just one.
* Updated documentation.

### Added

* Added a new AOH calculation function that works on a single classified habit or land cover input layer.

## v1.1.2 (12/01/2026)

### Changed

* Changed highest supported GDAL from 3.11.x to 3.12.x.
* Clean up species info data when exporting it.

### Fixed

* Instruct mypy to ignore GDAL for typing.

## v1.1.1 (02/12/2025)

### Changed

* Update to newer Yirgacheffe APIs to simplify code.
* Ensure reprojected habitat layers are pixel aligned for consistency.

## v1.1.0 (11/11/2025)

### Added

* Implementation of point validation based on [Dahal et al](https://gmd.copernicus.org/articles/15/5093/2022/).

### Changed

* Performance improvements and simplification to habitat processing.
* Store more analysis data from model validation.
* Improve performance of GBIF occurrence data fetches.

### Fixed

* Fixed a bug in collate data where it would fail to process any files.

## v1.0.1 (19/10/2025)

### Fixed

* Fixed github action for publishing to pip.

## v1.0.0 (19/10/2025)

### Added

* Initial release as stand alone package.
