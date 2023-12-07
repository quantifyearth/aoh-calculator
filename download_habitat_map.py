import argparse
import os
import sys

import pyshark
import requests
import zenodo_search as zsearch

DOI = "doi:6904020"
FILENAME = "lumbierres-10-5281_zenodo-5146073-v2.tif"

def main() -> None:
    parser = argparse.ArgumentParser(description="Resource downloader.")
    parser.add_argument(
        '--output_directory',
        type=str,
        help='directory where area geotiff should be stored',
        required=False,
        dest='results_path',
        default=".",
    )
    args = parser.parse_args()

    records = zsearch.search(DOI)
    if len(records) != 1:
        print(f"Failed to find {DOI} on Zenodo, expected 1 record, got {len(records)}", file=sys.stderr)
        sys.exit(-1)

    record = records[0]
    url = None
    for file in record.files:
        if file["key"] != FILENAME:
            continue
        try:
            url = file["links"]["self"]
        except KeyError:
            pass
        break
    if url is None:
        print(f"Failed to find URL for download in Zenodo response", file=sys.stderr)
        sys.exit(-1)

    # Note that zenodo file paths can have subdirs in them
    target_file = os.path.join(args.results_path, file["key"])
    results_directory, filename = os.path.split(target_file)
    os.makedirs(results_directory, exist_ok=True)

    with requests.get(url, stream=True) as response:
        with open(target_file, "wb") as download:
            for chunk in response.iter_content(chunk_size=1024*1024):
                download.write(chunk)


if __name__ == "__main__":
    main()
