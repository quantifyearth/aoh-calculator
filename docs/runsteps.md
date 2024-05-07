# How to run the pipeline

## Building the environment

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

## Fetching required data

To calculate the AoH we need various basemaps:

* A habitat map, which contains the habitat per pixel
* An elevation map, which has the height per pixel in meters

Both these maps must be at the same pixel spacing and projection, and the output AoH maps will be at that same pixel resolution and projection.

Habitat maps store habitat types in int types typically, the IUCN range data for species are of the form 'x.y' or 'x.y.z', and so you will need to also get a crosswalk table that maps between the IUCN ranges for the species and the particular habitat map you are using.

Here we present the steps required to fetch the [Lumbierres](https://zenodo.org/records/6904020) base maps, as recommended by the IUCN working group for generating the AoH basemaps for Terrestial species in STAR.

### Fetching the habitat map

To assist with provenance, we download the data from the Zenodo ID.

```shark-run:canned
python3 ./download_zenodo_raster.py --zenodo_id 6904020 --output /data/habitat.tif
```

For the corresponding crosswalk table we can use the one already defined:

```shark-run:canned
git clone https://github.com/prioritizr/aoh.git /data/prioritizr-aoh/
cd /data/prioritizr-aoh/
git checkout 34ae0912028581d6cf3d2b4e1fd68f81bc095f18
```

The habitat map by Lumbierres et al is at 100m resolution in World Berhman projection, and for IUCN AoH maps we use Molleide at 1KM resolution, so we use GDAL to do the resampling for this:

```shark-run:gdalonly
gdalwarp -t_srs ESRI:54009 -tr 1000 -1000 -r nearest -co COMPRESS=LZW -wo NUM_THREADS=40 /data/habitat.tif /data/habitat-1k.tif
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

Rather than calculate from a single main input source of IUCN data (which no matter what method is used - download from the website, API queries, etc. - tends to result in a single blob), we first split out the data into a single GeoJSON file per species per season:

```shark-run:aohbuilder
python3 ./extract_data_per_species.py --speciesdata /data/test_species_hab_elev.geojson \
                                      --projection "ESRI:54009" \
                                      --output /data/species-info/
```

The reason for doing this primarly one of pipeline optimisation, though it also makes the tasks of debugging and provenance tracing much easier. Most build systems, including the one we use, let you notice when files have updated and only do the work required based on that update. If we have many thousands of species on the redlise and only a few update, if we base our calculation on a single file with all species in, we'll have to calculate all thousands of results. But with this step added in, we will re-generate the per species per season GeoJSON files, which is cheap, but then we can spot that most of them haven't changed and we don't need to then calculate the rasters for those ones in the next stage.

```shark-publish
/data/species-info/
```

### Calculate AoH

This step generates a single AoH raster for a single one of the above GeoJSON files.

```shark-run:aohbuilder
python3 ./aohcalc.py --habitat /data/habitat-1k.tif \
                     --elevation-min /data/elevation-min-1k.tif \
                     --elevation-max /data/elevation-max-1k.tif \
                     --crosswalk /data/prioritizr-aoh/data-raw/crosswalk-lumb-cgls-data.csv \
                     --speciesdata /data/species-info/* \
                     --output /data/aohs/
```

The results you then want will all be in:

```shark-publish
/data/aohs/
```