import argparse
import operator
import os
import resource
import sys
import tempfile
import time
from functools import reduce
from pathlib import Path
from multiprocessing import Manager, Process, Queue, cpu_count

import yirgacheffe as yg

def stage_1_worker(
    filename: str,
    result_dir: str,
    input_queue: Queue,
) -> None:
    output_tif = os.path.join(result_dir, filename)

    merged_result = 0

    # We will open a lot of files here. Kanske Yirgacheffe should do something
    # here.
    _, max_fd_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (max_fd_limit, max_fd_limit))

    while True:
        # The expectation is the input is a list of seasonal rasters
        # for the same species (typically just one, not always)
        raster_paths = input_queue.get()
        if raster_paths is None:
            break

        rasters = [yg.read_raster(x) for x in raster_paths]
        binary_species_layer = reduce(operator.or_, [x != 0.0 for x in rasters])
        merged_result = binary_species_layer + merged_result

    if merged_result:
        merged_result.to_geotiff(output_tif) # type: ignore

def stage_2_worker(
    filename: str,
    result_dir: Path,
    input_queue: Queue,
) -> None:
    output_tif = result_dir / filename

    merged_result = 0

    while True:
        path = input_queue.get()
        if path is None:
            break

        partial_raster = yg.read_raster(path)
        merged_result = merged_result + partial_raster

    if merged_result:
        merged_result.to_geotiff(output_tif, nodata=0) # type: ignore

def species_richness(
    aohs_dir: Path,
    output_path: Path,
    processes_count: int
) -> None:
    os.makedirs(output_path.parent, exist_ok=True)

    aohs = list(Path(aohs_dir).rglob('*.tif'))
    print(f"We found {len(list(aohs))} AoH rasters")

    species_rasters : dict[str,set[Path]] = {}
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
