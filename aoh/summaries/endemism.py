# Endemism is the geometric mean of the proportion of how much each cell contributes to a species total AoH.
# Uses the trick from https://stackoverflow.com/questions/43099542/python-easy-way-to-do-geometric-mean-in-python
# for calculating the geometric mean with less risk of overflow

import argparse
import os
import resource
import sys
import tempfile
import time
from importlib.metadata import version
from pathlib import Path
from multiprocessing import Manager, Process, Queue, cpu_count
from typing import Dict, Optional, Set

import numpy as np
import yirgacheffe as yg

from .. import IUCNFormatFilename

def geometric_sum(raster: yg.YirgacheffeLayer) -> Optional[yg.YirgacheffeLayer]:
    aoh = raster.sum()
    if aoh > 0.0:
        return yg.log(yg.where(raster == 0.0, float('nan'), raster) / aoh)
    return None

def stage_1_worker(
    filename: str,
    result_dir: Path,
    input_queue: Queue,
) -> None:
    output_tif = result_dir / filename

    # We will open a lot of files here. Kanske Yirgacheffe should do something
    # here.
    _, max_fd_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (max_fd_limit, max_fd_limit))

    partials = []
    while True:
        raster_paths = input_queue.get()
        if raster_paths is None:
            break

        rasters = [yg.read_raster(x) for x in raster_paths]

        match len(rasters):
            case 2:
                sums = tuple(geometric_sum(r) for r in rasters)

                match sums:
                    case None, None:
                        continue
                    case a, None:
                        assert a is not None # keep mypy happy
                        partial = a.nan_to_num()
                    case None, b:
                        assert b is not None # keep mypy happy
                        partial = b.nan_to_num()
                    case s1, s2:
                        assert s1 is not None # keep mypy happy
                        assert s2 is not None # keep mypy happy
                        levelled_s1 = s1.nan_to_num(nan=np.inf * -1)
                        levelled_s2 = s2.nan_to_num(nan=np.inf * -1)
                        levelled_combined = yg.maximum(levelled_s1, levelled_s2)
                        partial = levelled_combined.nan_to_num(neginf=0.0)
            case 1:
                summed = geometric_sum(rasters[0])
                if summed is not None:
                    partial = summed.nan_to_num()
                else:
                    continue
            case _:
                raise ValueError("too many seasons")

        partials.append(partial)

    if partials:
        final = yg.sum(partials)
        final.to_geotiff(output_tif)


def stage_2_worker(
    filename: str,
    result_dir: Path,
    input_queue: Queue,
) -> None:
    output_tif = result_dir / filename

    partials = []

    while True:
        path = input_queue.get()
        if path is None:
            break
        partials.append(yg.read_raster(path))

    if partials:
        final = yg.sum(partials)
        final.to_geotiff(output_tif)

def endemism(
    aohs_dir: Path,
    species_richness_path: Path,
    output_path: Path,
    processes_count: int
) -> None:
    os.makedirs(output_path.parent, exist_ok=True)

    aohs = list(aohs_dir.glob("**/*.tif"))
    print(f"We found {len(aohs)} AoH rasters")

    species_rasters : Dict[int,Set[Path]] = {}
    for raster_path in aohs:
        parts = IUCNFormatFilename.of_filename(raster_path)
        speciesid = parts.taxon_id
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
                "summed_proportion.tif",
                Path(tempdir),
                source_queue
            ))
            single_worker.start()
            nextfiles = Path(tempdir).glob("*.tif")
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

        with yg.read_raster(species_richness_path) as species_richness:
            with yg.read_raster(os.path.join(tempdir, "summed_proportion.tif")) as summed_proportion:
                cleaned_species_richness = yg.where(species_richness > 0, species_richness, float('nan'))
                endemism_final = yg.exp(summed_proportion / cleaned_species_richness)
                endemism_final.to_geotiff(output_path, nodata=np.nan)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate species endemism")
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {version("aoh")}'
    )
    parser.add_argument(
        "--aohs_folder",
        type=Path,
        required=True,
        dest="aohs",
        help="Folder containing set of AoHs"
    )
    parser.add_argument(
        "--species_richness",
        type=Path,
        required=True,
        dest="species_richness",
        help="GeoTIFF containing species richness"
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

    endemism(
        args.aohs,
        args.species_richness,
        args.output,
        args.processes_count
    )

if __name__ == "__main__":
    main()
