import pandas as pd

ELEVATION_MIN = -500
ELEVATION_MAX = 9000

def tidy_data(row: pd.Series) -> pd.Series:
    """Tidy up the data as per Busana et als"""

    if row.elevation_lower is None:
        row.elevation_lower = ELEVATION_MIN
    if row.elevation_upper is None:
        row.elevation_upper = ELEVATION_MAX
    if row.elevation_lower > row.elevation_upper:
        low = row.elevation_lower
        row.elevation_lower = row.elevation_upper
        row.elevation_upper = low
    row.elevation_lower = max(ELEVATION_MIN, row.elevation_lower)
    row.elevation_upper = min(ELEVATION_MAX, row.elevation_upper)

    return row
