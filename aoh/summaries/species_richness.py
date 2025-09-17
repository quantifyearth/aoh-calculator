import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from multiprocessing import Manager, Process, Queue, cpu_count
from typing import Dict, Set

from yirgacheffe.layers import RasterLayer  # type: ignore
from yirgacheffe.operators import DataType  # type: ignore

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

        if len(rasters) > 1:
            union = RasterLayer.find_union(rasters)
            for r in rasters:
                r.set_window_for_union(union)
            calc = rasters[0] != 0.0
            for r in rasters[1:]:
                calc = calc | (r != 0.0)
        else:
            calc = rasters[0] != 0.0
        partial = RasterLayer.empty_raster_layer_like(rasters[0], datatype=DataType.UInt16)
        calc.save(partial)

        if merged_result is None:
            merged_result = partial
        else:
            merged_result.reset_window()

            union = RasterLayer.find_union([merged_result, partial])
            partial.set_window_for_union(union)
            merged_result.set_window_for_union(union)

            merged_calc = partial + merged_result
            temp = RasterLayer.empty_raster_layer_like(merged_result)
            merged_calc.save(temp)
            merged_result = temp

    if merged_result is not None:
        final = RasterLayer.empty_raster_layer_like(merged_result, filename=output_tif)
        merged_result.save(final)

def stage_2_worker(
    filename: str,
    result_dir: Path,
    input_queue: Queue,
) -> None:
    output_tif = result_dir / filename

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
        final = RasterLayer.empty_raster_layer_like(merged_result, filename=output_tif, nodata=0)
        merged_result.save(final)

def species_richness(
    aohs_dir: Path,
    output_path: Path,
    processes_count: int
) -> None:
    os.makedirs(output_path.parent, exist_ok=True)

    aohs = list(Path(aohs_dir).rglob('*.tif'))
    print(f"We found {len(list(aohs))} AoH rasters")

    species_rasters : Dict[str,Set[Path]] = {}
    for raster_path in aohs:
        speciesid = raster_path.name.split('_')[0]
        species_rasters[speciesid] = species_rasters.get(speciesid, set()).union({raster_path})
    print(f"Species detected: {len(species_rasters)} ")

    with tempfile.TemporaryDirectory() as tempdir:
        with Manager() as manager:
            source_queue = manager.Queue()

            workers = [Process(target=stage_1_worker, args=(
                f"{index}.tif",
                Path(tempdir),
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
                output_path.name,
                output_path.parent,
                source_queue
            ))
            single_worker.start()
            nextfiles = Path(tempdir).rglob('*.tif')
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

def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate species richness")
    parser.add_argument(
        "--aohs_folder",
        type=Path,
        required=True,
        dest="aohs",
        help="Folder containing set of AoHs"
    )
    parser.add_argument(
        "--output",
        type=Path,
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

    species_richness(
        args.aohs,
        args.output,
        args.processes_count
    )

if __name__ == "__main__":
    main()
