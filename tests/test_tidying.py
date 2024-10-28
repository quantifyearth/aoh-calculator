import pandas as pd
import pytest

from cleaning import tidy_data

@pytest.mark.parametrize("value,expected",
    [
        ((0.0, 100.0), (0.0, 100.0)),
        ((0.0, 1.0), (-25.0, 26.0)),
        ((None, 1.0), (-500.0, 1.0)),
        ((0.0, None), (0.0, 9000.0)),
        ((10000.0, None), (-500.0, 9000.0)),
        ((None, -600.0), (-500.0, 9000.0)),
        ((1.0, 0.0), (-500.0, 9000.0)),
        ((-1000.0, 1.0), (-500.0, 1.0)),
        ((0.0, 10000.0), (0.0, 9000.0)),
        ((1010.0, 1020.0), (990.0, 1040.0)),
        ((-500.0, -490.0), (-500.0, -450.0)),
        ((-600.0, -490.0), (-500.0, -450.0)),
    ]
)
def test_elevation_tidy(value, expected):
    row = pd.Series(value, ["elevation_lower", "elevation_upper"])
    updated = tidy_data(row)
    assert (updated.elevation_lower, updated.elevation_upper) == expected
