import pandas as pd
import pytest

from cleaning import tidy_data

@pytest.mark.parametrize("input,expected",
    [
        ((0.0, 1.0), (0.0, 1.0)),
        ((None, 1.0), (-500.0, 1.0)),
        ((0.0, None), (0.0, 9000.0)),
        ((1.0, 0.0), (0.0, 1.0)),
        ((-1000.0, 1.0), (-500.0, 1.0)),
        ((0.0, 10000.0), (0.0, 9000.0)),
    ]
)
def test_elevation_tidy(input, expected):
    row = pd.Series(input, ["elevation_lower", "elevation_upper"])
    updated = tidy_data(row)
    assert (updated.elevation_lower, updated.elevation_upper) == expected
