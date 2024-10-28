import math

import pandas as pd

ELEVATION_MIN = -500
ELEVATION_MAX = 9000

def tidy_data(row: pd.Series) -> pd.Series:
    """Tidy up the data as per Busana et al"""

    # Lower elevation higher than upper elevation
    if not pd.isna(row.elevation_lower) and not pd.isna(row.elevation_upper):
        if row.elevation_lower > row.elevation_upper:
            row.elevation_lower = ELEVATION_MIN
            row.elevation_upper = ELEVATION_MAX

    # Missing lower and/or upper elevation
    if pd.isna(row.elevation_lower):
        row.elevation_lower = ELEVATION_MIN
        if not pd.isna(row.elevation_upper) and row.elevation_upper < ELEVATION_MIN:
            row.elevation_upper = ELEVATION_MAX
    if pd.isna(row.elevation_upper):
        row.elevation_upper = ELEVATION_MAX
        if row.elevation_lower > ELEVATION_MAX:
            row.elevation_lower = ELEVATION_MIN

    # Lower elevation < -500 and/or upper elevation > 9000
    row.elevation_lower = max(ELEVATION_MIN, row.elevation_lower)
    row.elevation_upper = min(ELEVATION_MAX, row.elevation_upper)

    # Small difference (<50m) between lower and upper elevation
    elevation_diff = row.elevation_upper - row.elevation_lower
    if elevation_diff < 50:
        spare = 50 - elevation_diff
        adjust = math.ceil(spare / 2)
        row.elevation_lower -= adjust
        row.elevation_upper += adjust

        if row.elevation_lower < ELEVATION_MIN:
            adjust = ELEVATION_MIN - row.elevation_lower
            row.elevation_lower += adjust
            row.elevation_upper += adjust
        elif row.elevation_upper > ELEVATION_MAX:
            adjust = row.elevation_upper - ELEVATION_MAX
            row.elevation_lower -= adjust
            row.elevation_upper -= adjust

    return row
