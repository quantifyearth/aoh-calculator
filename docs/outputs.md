For each AOH calculation two files will be generated:

* A GeoTIFF with the name `aoh_T{species id}A{assessment id}_{season}.tif`
* A JSON file with the name `aoh_T{species id}A{assessment id}_{season}.json`

The GeoTIFF will not exist if there was an error processing the species data. There should always be a JSON file.

The JSON file contains information about the species that was being processed, summary statistics on the AOH (total area, etc.), and if the AOH wasn't calculated an error message as to why.
