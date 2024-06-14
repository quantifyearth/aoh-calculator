# How to run the pipeline for LIFE

## Build the environment


### The geospatial compute container

The dockerfile that comes with the repo should be used to run the pipeline.

```
docker build . -tag aohbuilder
```

For use with the [shark pipeline](https://github.com/quantifyearth/shark), we need this block to trigger a build currently:

```shark-build:aohbuilder
((from carboncredits/aohbuilder)
 (copy (src "./") (dst "/root/"))
 (workdir "/root/")
)
```

```shark-build:canned
((from aohbuilder))
```

For the projection changesd we use a barebones GDAL container. The reason for this is that these operations are expensive, and we don't want to re-execute them if we update our code.

```shark-build:gdalonly
((from ghcr.io/osgeo/gdal:ubuntu-small-3.8.1))
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

## Fetching the required data

To calculate the AoH we need various basemaps:

* Habitat maps for four scenarios:
    * Current day, in both L1 and L2 IUCN habitat classification
    * Potential Natural Vegetation (PNV) showing the habitats predicted without human intevention
    * Restore scenario - a map derived from the PNV and current maps showing certain lands restored to their pre-human
    * Conserve scenario - a map derived form current indicating the impact of placement of arable lands
* The Digital Elevation Map (DEM) which has the height per pixel in meters

All these maps must be at the same pixel spacing and projection, and the output AoH maps will be at that same pixel resolution and projection.

Habitat maps store habitat types in int types typically, the IUCN range data for species are of the form 'x.y' or 'x.y.z', and so you will need to also get a crosswalk table that maps between the IUCN ranges for the species and the particular habitat map you are using.

### Fetching the habitat maps

LIFE uses the work of Jung et al to get both the [current day habitat map](https://zenodo.org/records/4058819) and the [PNV habitat map](https://zenodo.org/records/4038749).

To assist with provenance, we download the data from the Zenodo ID.

```shark-run:canned
python3 ./download_zenodo_raster.py --zenodo_id 4038749 \
                                    --filename pnv_lvl1_004.zip \
                                    --extract --output /data/habitat/pnv_raw.tif
python3 ./download_zenodo_raster.py --zenodo_id 4058819 \
                                    --filename iucn_habitatclassification_composite_lvl2_ver004.zip \
                                    --extract --output /data/habitat/jung_l2_raw.tif
```

For the corresponding crosswalk table we can use the one already defined:

```shark-run:canned
git clone https://github.com/prioritizr/aoh.git /data/prioritizr-aoh/
cd /data/prioritizr-aoh/
git checkout 34ae0912028581d6cf3d2b4e1fd68f81bc095f18
```

The PNV map is only classified at Level 1 of the IUCN habitat codes, and so to match this non-artificial habitats in the L2 map are converted, as per Eyres et al:

| The current layer maps IUCN level 1 and 2 habitats, but habitats in the PNV layer are mapped only at IUCN level 1, so to estimate species’ proportion of original AOH now remaining we could only use natural habitats mapped at level 1 and artificial habitats at level 2.

```shark-run:canned
python3 ./LIFE/make_current_map.py --jung /data/habitat/jung_l2_raw.tif \
                                   --crosswalk /data/prioritizr-aoh/aoh/data-raw/crosswalk-jung-lvl2-data.csv \
                                   --output /data/habitat/current_raw.tif
```

The habitat map by Jung et al is at 100m resolution in World Berhman projection, and for IUCN compatible AoH maps we use Molleide at 1KM resolution, so we use GDAL to do the resampling for this:

```shark-run:gdalonly
gdalwarp -t_srs ESRI:54009 -tr 1000 -1000 -r nearest -co COMPRESS=LZW -wo NUM_THREADS=40 /data/habitat/pnv_raw.tif /data/habitat/pnv.tif
gdalwarp -t_srs ESRI:54009 -tr 1000 -1000 -r nearest -co COMPRESS=LZW -wo NUM_THREADS=40 /data/habitat/current_raw.tif /data/habitat/current.tif
```



### Generating additional habitat maps

From [Eyres et al]():

For the restoration map:

| In the restoration scenario all areas classified as arable or pasture were restored to their PNV.

```shark-run:canned
python3 ./LIFE/make_restore_map.py --pnv /data/habitat/pnv.tif \
                                   --current /data/habitat/current.tif \
                                   --crosswalk /data/prioritizr-aoh/aoh/data-raw/crosswalk-jung-lvl2-data.csv \
                                   --output /data/habitat/restore.tif
```

For the conservation map:

| In the conversion scenario all habitats currently mapped as natural or pasture were converted to arable land.

```shark-run:canned
python3 ./LIFE/make_arable_map.py --current /data/habitat/current.tif \
                                  --crosswalk /data/prioritizr-aoh/aoh/data-raw/crosswalk-jung-lvl2-data.csv \
                                  --output /data/habitat/arable.tif
```


### Fetching the elevation map

To assist with provenance, we download the data from the Zenodo ID.

```shark-run:canned
python3 ./download_zenodo_raster.py --zenodo_id 5719984 --output /data/elevation.tif
```

Similarly to the habitat map we need to resample to 1km, however rather than picking the mean elevation, we select both the min and max elevation for each pixel, and then check whether the species is in that range when we calculate AoH.

```shark-run:gdalonly
gdalwarp -t_srs ESRI:54009 -tr 1000 -1000 -r min -co COMPRESS=LZW -wo NUM_THREADS=40 /data/elevation.tif /data/elevation-min-1k.tif
gdalwarp -t_srs ESRI:54009 -tr 1000 -1000 -r max -co COMPRESS=LZW -wo NUM_THREADS=40 /data/elevation.tif /data/elevation-max-1k.tif
```

### Fetching the species ranges

This sections needs to be improved! This is some canned test data from the IUCN dataset. We do have a download pipeline as part of LIFE, but it's not been merged into here yet as we're chatting to the IUCN about the best way to achieve this.

```shark-run:aohbuilder
curl -o /data/test_species_hab_elev.geojson https://digitalflapjack.com/data/test_species_hab_elev.geojson
```


## Calculating AoH

Once all the data has been collected, we can now calclate the AoH maps.

### Get per species range data

Rather than calculate from the postgis database directly, we first split out the data into a single GeoJSON file per species per season:

```shark-run:postgis
export DB_HOST=somehost
export DB_USER=username
export DB_PASSWORD=secretpassword
export DB_NAME=iucnredlist

python3 ./extract_species_data_psql.py --output /data/species-info/ --projection "ESRI:54009"
```

The reason for doing this primarly one of pipeline optimisation, though it also makes the tasks of debugging and provenance tracing much easier. Most build systems, including the one we use, let you notice when files have updated and only do the work required based on that update. If we have many thousands of species on the redlise and only a few update, if we base our calculation on a single file with all species in, we'll have to calculate all thousands of results. But with this step added in, we will re-generate the per species per season GeoJSON files, which is cheap, but then we can spot that most of them haven't changed and we don't need to then calculate the rasters for those ones in the next stage.

```shark-publish
/data/species-info/
```