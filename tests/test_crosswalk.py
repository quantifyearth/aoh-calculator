import tempfile
from pathlib import Path
from typing import Set

import pytest

from aoh._internal.speciesinfo import load_crosswalk_table, crosswalk_habitats

EXAMPLE_CROSSWALK = """code,value
1,100
1,101
1,102
1.1,100
1.1,101
1.2,100
1.2,102
2,200
2,201
2,202
2.1,200
2.1,201
2.2,200
2.2,202
"""
EXPECTED_CROSSWALK = {
    '1.0': [100, 101, 102],
    '1.1': [100, 101],
    '1.2': [100, 102],
    '2.0': [200, 201, 202],
    '2.1': [200, 201],
    '2.2': [200, 202],
}

def test_load_simple_life_crosswalk() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        crosswalk_path = Path(tmpdir) / "crosswalk.csv"
        with open(crosswalk_path, "w", encoding="UTF-8") as f:
            f.write(EXAMPLE_CROSSWALK)
        crosswalk = load_crosswalk_table(crosswalk_path)
    assert crosswalk == EXPECTED_CROSSWALK

def test_fails_with_bad_file() -> None:
    with pytest.raises(FileNotFoundError):
        _ = load_crosswalk_table(Path("/this/does/not/exist"))

@pytest.mark.parametrize("value,expected", [
    ({"1.0"}, {100, 101, 102}),
    ({"1.1", "2.1"}, {100, 101, 200, 201}),
    (set(), set()),
    ({"foo"}, set()),
    ({"1.2", "foo"}, {100, 102}),
])
def test_crosswalk_with_coverage(value: Set[str], expected: Set[int]) -> None:
    result = crosswalk_habitats(EXPECTED_CROSSWALK, value)
    assert result == expected
