import argparse
import gzip
import io
import os
import shutil
import sys
import tempfile
import zipfile
from http import HTTPStatus

import pyshark # pylint: disable=W0611
import requests

def main() -> None:
    parser = argparse.ArgumentParser(description="Zenodo resource downloader.")
    parser.add_argument(
        '--zenodo_id',
        type=int,
        help='ID of Zenodo page',
        required=True,
        dest='zenodo_id',
    )
    parser.add_argument(
        '--filename',
        type=str,
        help='Filename of the resource. If ommitted download first resource.',
        required=False,
        dest='filename',
    )
    parser.add_argument(
        '--extract',
        help="Extract zip file automatically",
        default=False,
        required=False,
        action='store_true',
        dest='extract',
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Path where resource should be stored',
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
        if args.filename and filename != args.filename:
            continue
        try:
            url = file["links"]["self"]
        except KeyError:
            pass
        break
    if url is None:
        print("Failed to find URL for download in Zenodo response", file=sys.stderr)
        sys.exit(-1)

    with tempfile.TemporaryDirectory() as tempdir:
        target = os.path.join(tempdir, "download")
        with requests.get(url, stream=True, timeout=60) as response:
            if args.extract:
                try:
                    with zipfile.ZipFile(io.BytesIO(response.content)) as zipf:
                        members = zipf.namelist()
                        target = zipf.extract(members[0], path=tempdir)
                except zipfile.BadZipFile:
                    try:
                        reader = gzip.GzipFile(fileobj=io.BytesIO(response.content))
                        with open(target, "wb") as download:
                            shutil.copyfileobj(reader, download)
                    except gzip.BadGzipFile:
                        print(f"Failed to extract data for {url}", file=sys.stderr)
                        sys.exit(-1)
            else:
                with open(target, "wb") as download:
                    for chunk in response.iter_content(chunk_size=1024*1024):
                        download.write(chunk)

        # Note that zenodo file paths can have subdirs in them
        results_directory, _ = os.path.split(args.results_path)
        os.makedirs(results_directory, exist_ok=True)

        try:
            os.rename(target, args.results_path)
        except OSError:
            shutil.copy(target, args.results_path)


if __name__ == "__main__":
    main()
