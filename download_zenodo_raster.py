import argparse
import json
import os
import sys
from http import HTTPStatus

import pyshark
import requests

def main() -> None:
    parser = argparse.ArgumentParser(description="Resource downloader.")
    parser.add_argument(
        '--zenodo_id',
        type=int,
        help='ID of Zenodo page',
        required=True,
        dest='zenodo_id',
    )
    parser.add_argument(
        '--output_directory',
        type=str,
        help='directory where area geotiff should be stored',
        required=False,
        dest='results_path',
        default=".",
    )
    args = parser.parse_args()

    response = requests.get(f'https://zenodo.org/api/records/{args.zenodo_id}')
    if response.status_code != HTTPStatus.OK:
        printf(f"Got a {response.status_code} response from zenodo", file=sys.stderr)
        sys.exit(-1)
    record = response.json()

    url = None
    filename = None
    for file in record["files"]:
        filename = file["key"]
        _, ext = os.path.splitext(filename)
        if ext != ".tif":
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
    target_file = os.path.join(args.results_path, filename)
    results_directory, filename = os.path.split(target_file)
    os.makedirs(results_directory, exist_ok=True)

    with requests.get(url, stream=True) as response:
        with open(target_file, "wb") as download:
            for chunk in response.iter_content(chunk_size=1024*1024):
                download.write(chunk)


if __name__ == "__main__":
    main()
