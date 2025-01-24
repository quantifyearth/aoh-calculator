# Endemism is the geometric mean of the proportion of how much each cell contributes to a species total AoH.
# Uses the trick from https://stackoverflow.com/questions/43099542/python-easy-way-to-do-geometric-mean-in-python
# for calculating the geometric mean with less risk of overflow

import argparse
import os
import sys
import tempfile
import time
from glob import glob
from multiprocessing import Manager, Process, Queue, cpu_count

import numpy as np
from osgeo import gdal
from yirgacheffe.layers import RasterLayer
import yirgacheffe.operators as yo

def geometric_sum(raster: RasterLayer):
    aoh = raster.sum()
    if aoh > 0.0:
        return yo.log(yo.where(raster == 0.0, float('nan'), raster) / aoh)
    return None

def stage_1_worker(
    filename: str,
    result_dir: str,
    input_queue: Queue,
) -> None:
    output_tif = os.path.join(result_dir, filename)

    merged_result = None

    while True:
        raster_paths = input_queue.get()
        if raster_paths is None:
            break

        rasters = [RasterLayer.layer_from_file(x) for x in raster_paths]

        match len(rasters):
            case 2:
                union = RasterLayer.find_union(rasters)
                for r in rasters:
                    r.set_window_for_union(union)

                sums = tuple(geometric_sum(r) for r in rasters)

                match sums:
                    case None, None:
                        continue
                    case a, None:
                        combined = a.nan_to_num()
                    case None, b:
                        combined = b.nan_to_num()
                    case s1, s2:
                        levelled_s1 = s1.nan_to_num(nan=np.inf * -1)
                        levelled_s2 = s2.nan_to_num(nan=np.inf * -1)
                        levelled_combined = yo.maximum(levelled_s1, levelled_s2)
                        combined = levelled_combined.nan_to_num(neginf=0.0)


                partial = RasterLayer.empty_raster_layer_like(rasters[0], datatype=gdal.GDT_Float64)
                combined.save(partial)
            case 1:
                summed = geometric_sum(rasters[0])
                if summed is not None:
                    partial = RasterLayer.empty_raster_layer_like(rasters[0], datatype=gdal.GDT_Float64)
                    summed.nan_to_num().save(partial)
                else:
                    continue
            case _:
                raise ValueError("too many seasons")

        if merged_result is None:
            merged_result = partial
        else:
            merged_result.reset_window()

            union = RasterLayer.find_union([merged_result, partial])
            partial.set_window_for_union(union)
            merged_result.set_window_for_union(union)

            merged = partial + merged_result
            temp = RasterLayer.empty_raster_layer_like(merged_result)
            merged.save(temp)
            merged_result = temp

    if merged_result is not None:
        final = RasterLayer.empty_raster_layer_like(merged_result, filename=output_tif)
        merged_result.save(final)

def stage_2_worker(
    filename: str,
    result_dir: str,
    input_queue: Queue,
) -> None:
    output_tif = os.path.join(result_dir, filename)

    merged_result = None

    while True:
        path = input_queue.get()
        if path is None:
            break

        with RasterLayer.layer_from_file(path) as partial_raster:
            if merged_result is None:
                merged_result = RasterLayer.empty_raster_layer_like(partial_raster)
                partial_raster.save(merged_result)
            else:
                merged_result.reset_window()

                union = RasterLayer.find_union([merged_result, partial_raster])
                merged_result.set_window_for_union(union)
                partial_raster.set_window_for_union(union)

                calc = merged_result + partial_raster
                temp = RasterLayer.empty_raster_layer_like(merged_result)
                calc.save(temp)
                merged_result = temp

    if merged_result:
        final = RasterLayer.empty_raster_layer_like(merged_result, filename=output_tif)
        merged_result.save(final)

def endemism(
    aohs_dir: str,
    species_richness_path: str,
    output_path: str,
    processes_count: int
) -> None:
    output_dir, _ = os.path.split(output_path)
    os.makedirs(output_dir, exist_ok=True)

    aohs = glob("**/*.tif", root_dir=aohs_dir)
    print(f"We found {len(aohs)} AoH rasters")

    species_rasters = {}
    for raster_path in aohs:
        speciesid = os.path.basename(raster_path).split('_')[0]
        full_path = os.path.join(aohs_dir, raster_path)
        species_rasters[speciesid] = species_rasters.get(speciesid, set()).union({full_path})
    print(f"Species detected: {len(species_rasters)} ")

    with tempfile.TemporaryDirectory() as tempdir:
        with Manager() as manager:
            source_queue = manager.Queue()

            workers = [Process(target=stage_1_worker, args=(
                f"{index}.tif",
                tempdir,
                source_queue
            )) for index in range(processes_count)]
            for worker_process in workers:
                worker_process.start()

            for _, raster_set in species_rasters.items():
                source_queue.put(raster_set)
            for _ in range(len(workers)):
                source_queue.put(None)

            processes = workers
            while processes:
                candidates = [x for x in processes if not x.is_alive()]
                for candidate in candidates:
                    candidate.join()
                    if candidate.exitcode:
                        for victim in processes:
                            victim.kill()
                        sys.exit(candidate.exitcode)
                    processes.remove(candidate)
                time.sleep(1)

            # here we should have now a set of images in tempdir to merge
            single_worker = Process(target=stage_2_worker, args=(
                "summed_proportion.tif",
                tempdir,
                source_queue
            ))
            single_worker.start()
            nextfiles = [os.path.join(tempdir, x) for x in glob("*.tif", root_dir=tempdir)]
            for file in nextfiles:
                source_queue.put(file)
            source_queue.put(None)

            processes = [single_worker]
            while processes:
                candidates = [x for x in processes if not x.is_alive()]
                for candidate in candidates:
                    candidate.join()
                    if candidate.exitcode:
                        for victim in processes:
                            victim.kill()
                        sys.exit(candidate.exitcode)
                    processes.remove(candidate)
                time.sleep(1)

        with RasterLayer.layer_from_file(species_richness_path) as species_richness:
            with RasterLayer.layer_from_file(os.path.join(tempdir, "summed_proportion.tif")) as summed_proportion:

                intersection = RasterLayer.find_intersection([summed_proportion, species_richness])
                summed_proportion.set_window_for_intersection(intersection)
                species_richness.set_window_for_intersection(intersection)

                cleaned_species_richness = yo.where(species_richness > 0, species_richness, float('nan'))

                with RasterLayer.empty_raster_layer_like(
                    summed_proportion,
                    filename=output_path,
                    nodata=np.nan
                ) as result:
                    calc = yo.exp(summed_proportion / cleaned_species_richness)
                    calc.save(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate species richness")
    parser.add_argument(
        "--aohs_folder",
        type=str,
        required=True,
        dest="aohs",
        help="Folder containing set of AoHs"
    )
    parser.add_argument(
        "--species_richness",
        type=str,
        required=True,
        dest="species_richness",
        help="GeoTIFF containing species richness"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        dest="output",
        help="Destination GeoTIFF file for results."
    )
    parser.add_argument(
        "-j",
        type=int,
        required=False,
        default=round(cpu_count() / 2),
        dest="processes_count",
        help="Number of concurrent threads to use."
    )
    args = parser.parse_args()

    endemism(
        args.aohs,
        args.species_richness,
        args.output,
        args.processes_count
    )

if __name__ == "__main__":
    main()
