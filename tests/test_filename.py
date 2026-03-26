from pathlib import Path
from typing import Any

import pytest

from aoh import IUCNFormatFilename

@pytest.mark.parametrize("filename, expected", [
    ("aoh_T42A123_all.tif", IUCNFormatFilename("aoh", 42, 123, "all", ".tif")),
    (Path("aoh_T42A123_all.tif"), IUCNFormatFilename("aoh", 42, 123, "all", ".tif")),
    ("/test/directory/aoh_T42A123_all.tif", IUCNFormatFilename("aoh", 42, 123, "all", ".tif")),
    (Path("/test/directory/aoh_T42A123_all.tif"), IUCNFormatFilename("aoh", 42, 123, "all", ".tif")),
    ("aoh_T42A123_all.json", IUCNFormatFilename("aoh", 42, 123, "all", ".json")),
    ("aoh_T42A123_vår.json", IUCNFormatFilename("aoh", 42, 123, "vår", ".json")),
    (Path("aoh_T42A123_vår.json"), IUCNFormatFilename("aoh", 42, 123, "vår", ".json")),
    ("aoh_T42A123.tif", IUCNFormatFilename("aoh", 42, 123, None, ".tif")),
    ("aoh_T42_all.tif", IUCNFormatFilename("aoh", 42, None, "all", ".tif")),
    ("aoh_T42.tif", IUCNFormatFilename("aoh", 42, None, None, ".tif")),
])
def test_valid_aoh_filename(filename : Path | str, expected: IUCNFormatFilename) -> None:
    res = IUCNFormatFilename.of_filename(filename)
    assert res == expected

@pytest.mark.parametrize("filename, exception", [
    (None, TypeError),
    (32, TypeError),
    ("malformed_filename.tif", ValueError),
])
def test_invalid_aoh_filename(filename: Any, exception: type[BaseException]) -> None:
    with pytest.raises(exception):
        _ = IUCNFormatFilename.of_filename(filename)

@pytest.mark.parametrize("filename, expected", [
    (IUCNFormatFilename("aoh", 42, 123, "all", ".tif"), Path("aoh_T42A123_all.tif")),
    (IUCNFormatFilename("aoh", 42, None, "all", ".tif"), Path("aoh_T42_all.tif")),
    (IUCNFormatFilename("aoh", 42, 123, None, ".tif"), Path("aoh_T42A123.tif")),
    (IUCNFormatFilename("aoh", 42, None, None, ".tif"), Path("aoh_T42.tif")),
])
def test_valid_build_filename(filename: IUCNFormatFilename, expected: Path) -> None:
    res = filename.to_path()
    assert res == expected
