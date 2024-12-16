import math

import pandas as pd

ELEVATION_MIN = -500
ELEVATION_MAX = 9000
ELEVATION_SEPERATION = 50

def tidy_data(
    row: pd.Series,
    elevation_max=ELEVATION_MAX,
    elevation_min=ELEVATION_MIN,
    elevation_seperation=ELEVATION_SEPERATION
) -> pd.Series:
    """Tidy up the data as per Daniele Busana et al"""

    # Lower elevation higher than upper elevation
    if not pd.isna(row.elevation_lower) and not pd.isna(row.elevation_upper):
        if row.elevation_lower > row.elevation_upper:
            row.elevation_lower = elevation_min
            row.elevation_upper = elevation_max

    # Missing lower and/or upper elevation
    if pd.isna(row.elevation_lower):
        row.elevation_lower = elevation_min
        if not pd.isna(row.elevation_upper) and row.elevation_upper < elevation_min:
            row.elevation_upper = elevation_max
    if pd.isna(row.elevation_upper):
        row.elevation_upper = elevation_max
        if row.elevation_lower > elevation_max:
            row.elevation_lower = elevation_min

    # Lower elevation < -500 and/or upper elevation > 9000
    row.elevation_lower = max(elevation_min, row.elevation_lower)
    row.elevation_upper = min(elevation_max, row.elevation_upper)

    # Small difference (<50m) between lower and upper elevation
    elevation_diff = row.elevation_upper - row.elevation_lower
    if elevation_diff < elevation_seperation:
        spare = elevation_seperation - elevation_diff
        adjust = math.ceil(spare / 2)
        row.elevation_lower -= adjust
        row.elevation_upper += adjust

        if row.elevation_lower < elevation_min:
            adjust = elevation_min - row.elevation_lower
            row.elevation_lower += adjust
            row.elevation_upper += adjust
        elif row.elevation_upper > elevation_max:
            adjust = row.elevation_upper - elevation_max
            row.elevation_lower -= adjust
            row.elevation_upper -= adjust

    return row
