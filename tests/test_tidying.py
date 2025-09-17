import pandas as pd
import pytest

from aoh.cleaning import tidy_data

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


@pytest.mark.parametrize("value,expected",
    [
        ((0.0, 100.0), (0.0, 100.0)),
        ((0.0, 1.0), (-6.0, 7.0)),
        ((None, 1.0), (-427.0, 1.0)),
        ((0.0, None), (0.0, 8580.0)),
        ((10000.0, None), (-427.0, 8580.0)),
        ((None, -600.0), (-427.0, 8580.0)),
        ((1.0, 0.0), (-427.0, 8580.0)),
        ((-1000.0, 1.0), (-427.0, 1.0)),
        ((0.0, 10000.0), (0.0, 8580.0)),
        ((1010.0, 1020.0), (1009.0, 1021.0)),
        ((-427.0, -420.0), (-427.0, -414.0)),
        ((-600.0, -490.0), (-427.0, -414.0)),
    ]
)
def test_elevation_tidy_different_bounds(value, expected):
    row = pd.Series(value, ["elevation_lower", "elevation_upper"])
    updated = tidy_data(
        row,
        elevation_max=8580,
        elevation_min=-427,
        elevation_seperation=12,
    )
    assert (updated.elevation_lower, updated.elevation_upper) == expected
