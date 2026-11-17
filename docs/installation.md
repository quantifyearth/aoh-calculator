## Prerequisites

You'll need GDAL installed on your system. The Python GDAL package version should match your system GDAL version. You can check your GDAL version with:

```bash
gdalinfo --version
```

Then install the matching Python package:

```bash
pip install gdal[numpy]==YOUR_VERSION_HERE
```


## Installation

The AOH Calculator is available as a Python package and can be installed via pip:

```bash
pip install aoh
```

This provides both command-line tools and a Python library for programmatic use.

For validation tools that require R, install with the validation extra:

```bash
pip install aoh[validation]
```

You will also need to following R packages installed: lme4, lmerTest, broom.mixed, emmeans, report, sklearn

