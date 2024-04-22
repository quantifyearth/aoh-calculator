# How to run the pipeline


## Building the environment

The dockerfile that comes with the repo should be used to run the pipeline. You can compile it thus:

```shark-build:aohbuilder
((from carboncredits/aohbuilder)
 (run (shell "echo 'Something for the log!'")))
```

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

Alternatively you can build your own python virtual env assuming you have everything required:

```
python3 -m virtualenv ./venv
. ./venv/bin/activate
pip install -r requirements.txt
```


## Fetching required data

To calculate the AoH we need various basemaps:

* A habitat map, which contains the habitat per pixel
* An elevation map, which has the height per pixel in meters

Both these maps must be at the same pixel spacing and projection, and the output AoH maps will be at that same pixel resolution and projection.

Habitat maps store habitat types in int types typically, the IUCN range data for species are of the form 'x.y' or 'x.y.z', and so you will need to also get a crosswalk table that maps between the IUCN ranges for the species and the particular habitat map you are using.

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

```shark-run:aohbuilder
python3 ./download_zenodo_raster.py --zenodo_id 5719984 --output /data/elevation.tif
```

### Fetching the species ranges


## Calculating AoH

### Get per species range data

```shark-run:postgis
export DB_HOST=somehost
export DB_USER=username
export DB_PASSWORD=secretpassword
export DB_NAME=iucnredlist

python3 ./extract_species_data_psql.py --output /data/species-info/
```

```shark-publish
/data/species-info/
```

### Calculate AoH

For each speces we run the following:

```shark-run:aohbuilder
python3 ./aohcalc.py --habitat /data/habitat.tif \
                     --elevation /data/elevation.tif \
                     --crosswalk /data/prioritizr-aoh/data-raw/crosswalk-lumb-cgls-data.csv \
                     --speciesdata /data/species-info/* \
                     --output /data/aohs/
```

```shark-publish
/data/aohs/
```
