"""
AOH Calculator - A library for calculating Area of Habitat for species distribution mapping.

This package provides tools for:
- Calculating Area of Habitat from species range and habitat data
- Processing habitat data for species analysis
- Species richness and endemism calculations
- Validation of habitat maps
"""

from pathlib import Path

import tomli as tomllib

from .cleaning import tidy_data

try:
    from importlib import metadata
    __version__: str = metadata.version(__name__)
except ModuleNotFoundError:
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)
    __version__ = pyproject_data["project"]["version"]

# Only export basic utilities by default
# Heavy dependencies are available via explicit imports
__all__ = [
    "tidy_data"
]
