# AoH Validation

This directory contains code to implement the model base validation proposed by [Dahal et al](https://gmd.copernicus.org/articles/15/5093/2022/). The model validation implementation cribs heavily from an R implementation by [Franchesca Ridley]().

This directory contains the following scripts:

* `collate_data.py` - Then you generate a series of AOH GeoTIFFs, besides each one is a JSON file that contains information required for validation. This script takes a folder containing the AOH output of a run and collates all those JSON files into a single CSV file that can be used for a validation run.
* `validate_map_prevalence.py` - This uses the data in the collated CSV to do a model validation as per the Dahal et al paper.
* `fetch_gbif_data.py` - This script takes the collated CSV file and attempts to find occurence data on GBIF that can be used for point validation as per the Dahal et al paper.
* `validate_occurences.py` - This uses the data fetched from GBIF to check the occurrences against a coprus of AOHs.
