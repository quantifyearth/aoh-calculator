import math

import pandas as pd

ELEVATION_MIN = -500
ELEVATION_MAX = 9000

def tidy_data(row: pd.Series) -> pd.Series:
    """Tidy up the data as per Busana et al"""

    # Missing lower and/or upper elevation
    if row.elevation_lower is None:
        row.elevation_lower = ELEVATION_MIN
    if row.elevation_upper is None:
        row.elevation_upper = ELEVATION_MAX

    # Lower elevation < -500 and/or upper elevation > 9000
    row.elevation_lower = max(ELEVATION_MIN, row.elevation_lower)
    row.elevation_upper = min(ELEVATION_MAX, row.elevation_upper)

    # Lower elevation higher than upper elevation
    if row.elevation_lower > row.elevation_upper:
        row.elevation_lower = ELEVATION_MIN
        row.elevation_upper = ELEVATION_MAX

    # Small difference (<50m) between lower and upper elevation
    elevation_diff = row.elevation_upper - row.elevation_lower
    if elevation_diff < 50.0:
        spare = 50.0 - elevation_diff
        adjust = math.ceil(spare / 2.0)
        row.elevation_lower -= adjust
        row.elevation_upper += adjust

    return row
