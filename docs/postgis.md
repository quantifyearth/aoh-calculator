# How to run the pipeline


## Building the environment

### The geospatial compute container

The dockerfile that comes with the repo should be used to run the compute parts of the pipeline.

```
docker build . -tag aohbuilder
```

For use with the [shark pipeline](https://github.com/quantifyearth/shark), we need this block to trigger a build currently:

```shark-build:aohbuilder
((from carboncredits/aohbuilder)
 (run (shell "echo 'Something for the log!'")))
```

Alternatively you can build your own python virtual env assuming you have everything required. For this you will need at least a GDAL version installed locally, and you may want to update requirements.txt to match the python GDAL bindings to the version you have installed.

```
python3 -m virtualenv ./venv
. ./venv/bin/activate
pip install -r requirements.txt
```

### The PostGIS container

For querying the IUCN data held in the PostGIS database we use a seperate container, based on the standard PostGIS image.

```shark-build:postgis
((from python:3.12-slim)
 (run (network host) (shell "apt-get update -qqy && apt-get -y install libpq-dev gcc git && rm -rf /var/lib/apt/lists/* && rm -rf /var/cache/apt/*"))
 (run (network host) (shell "pip install psycopg2 SQLalchemy geopandas"))
 (run (network host) (shell "pip install git+https://github.com/quantifyearth/pyshark"))
 (copy (src "./") (dst "/root/"))
 (workdir "/root/")
 (run (shell "chmod 755 *.py"))
)
```

## Fetching required data

To calculate the AoH we need various basemaps:

* A habitat map, which contains the habitat per pixel
* An elevation map, which has the height per pixel in meters

Both these maps must be at the same pixel spacing and projection, and the output AoH maps will be at that same pixel resolution and projection.

Habitat maps store habitat types in int types typically, the IUCN range data for species are of the form 'x.y' or 'x.y.z', and so you will need to also get a crosswalk table that maps between the IUCN ranges for the species and the particular habitat map you are using.

Here we present the steps required to fetch the [Lumbierres](https://zenodo.org/records/6904020) base maps.

### Fetching the habitat map

To assist with provenance, we download the data from the Zenodo ID.

```shark-run:aohbuilder
python3 ./download_zenodo_raster.py --zenodo_id 6904020 --output /data/habitat.tif
```

For the corresponding crosswalk table we can use the one already defined:

```shark-run:aohbuilder
git clone https://github.com/prioritizr/aoh.git /data/prioritizr-aoh
cd /data/prioritizr-aoh/
git checkout 34ae0912028581d6cf3d2b4e1fd68f81bc095f18
```

### Fetching the elevation map

To assist with provenance, we download the data from the Zenodo ID.

```shark-run:aohbuilder
python3 ./download_zenodo_raster.py --zenodo_id 5719984 --output /data/elevation.tif
```

### Fetching the species ranges

In this workflow we assume you have a PostGIS database set up with a clone of the IUCN redlist API data already in it, so there is nothing to do here.

## Calculating AoH

Once all the data has been collected, we can now calclate the AoH maps.

### Get per species range data

Rather than calculate from the postgis database directly, we first split out the data into a single GeoJSON file per species per season:

```shark-run:postgis
export DB_HOST=somehost
export DB_USER=username
export DB_PASSWORD=secretpassword
export DB_NAME=iucnredlist

python3 ./extract_species_data_psql.py --output /data/species-info/
```

The reason for doing this primarly one of pipeline optimisation, though it also makes the tasks of debugging and provenance tracing much easier. Most build systems, including the one we use, let you notice when files have updated and only do the work required based on that update. If we have many thousands of species on the redlise and only a few update, if we base our calculation on a single file with all species in, we'll have to calculate all thousands of results. But with this step added in, we will re-generate the per species per season GeoJSON files, which is cheap, but then we can spot that most of them haven't changed and we don't need to then calculate the rasters for those ones in the next stage.

```shark-publish
/data/species-info/
```


### Calculate AoH

This step generates a single AoH raster for a single one of the above GeoJSON files.

```shark-run:aohbuilder
python3 ./aohcalc.py --habitat /data/habitat.tif \
                     --elevation /data/elevation.tif \
                     --crosswalk /data/prioritizr-aoh/data-raw/crosswalk-lumb-cgls-data.csv \
                     --speciesdata /data/species-info/* \
                     --output /data/aohs/
```

The results you then want will all be in:

```shark-publish
/data/aohs/
```
