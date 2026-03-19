import operator
from functools import reduce
from pathlib import Path

import yirgacheffe as yg

def single_layer(path_or_constant: Path | str) -> yg.YirgacheffeLayer | float:
    try:
        # Most likely to be a raster or a shape file
        path = Path(path_or_constant)
        if path.suffix.lower() in {".gpkg", ".shp", ".geojson"}:
            return yg.read_shape(path)
        else:
            try:
                # This is for legacy reasons now: we used to use a one pixel
                # wide area per pixel raster for performance reasons before
                # we had the dynamically calculated version. I don't believe this
                # should be in use any more, but just in case
                return yg.read_narrow_raster(path)
            except ValueError:
                return yg.read_raster(path)
    except FileNotFoundError:
        # If we failed to load it as a file, was this meant to be a constant?
        return float(str(path_or_constant))

def load_weights(weight_layer_paths: list[Path] | list[str] | None) -> yg.YirgacheffeLayer | float | None:
    if weight_layer_paths is None or not weight_layer_paths:
        return None
    layers = [single_layer(x) for x in weight_layer_paths]
    return reduce(operator.mul, layers)
