import argparse
import os
import sys
from http import HTTPStatus

import pyshark # pylint: disable=W0611
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
        '--output',
        type=str,
        help='path where area geotiff should be stored',
        required=False,
        dest='results_path',
        default=".",
    )
    args = parser.parse_args()

    response = requests.get(f'https://zenodo.org/api/records/{args.zenodo_id}', timeout=60)
    if response.status_code != HTTPStatus.OK:
        print(f"Got a {response.status_code} response from zenodo", file=sys.stderr)
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
        print("Failed to find URL for download in Zenodo response", file=sys.stderr)
        sys.exit(-1)

    # Note that zenodo file paths can have subdirs in them
    results_directory, _ = os.path.split(args.results_path)
    os.makedirs(results_directory, exist_ok=True)

    with requests.get(url, stream=True, timeout=60) as response:
        with open(args.results_path, "wb") as download:
            for chunk in response.iter_content(chunk_size=1024*1024):
                download.write(chunk)

if __name__ == "__main__":
    main()
