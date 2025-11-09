import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Generate a synthetic 24h time series approximating hot day + afternoon peak


def synthetic_hourly_series(date: str):
    dt0 = datetime.fromisoformat(date)
    hours = pd.date_range(dt0, dt0 + timedelta(hours=23), freq="h")
    month = dt0.month
    # Basic seasonal scaling (southern US baseline)
    if month in (12, 1, 2):
        tmax, tmin = 18.0, 8.0
    elif month in (3, 4, 5):
        tmax, tmin = 28.0, 16.0
    elif month in (6, 7, 8):
        tmax, tmin = 38.0, 24.0
    else:
        tmax, tmin = 30.0, 18.0
    temp = (tmax + tmin) / 2 + ((tmax - tmin) / 2) * np.sin((hours.hour - 6) / 24 * 2 * np.pi)
    rh = 0.55 + 0.15 * np.sin((hours.hour) / 24 * 2 * np.pi)
    wind = 2.0 + 1.0 * np.cos((hours.hour) / 24 * 2 * np.pi)
    glob_rad = np.clip(800 * np.sin((hours.hour) / 24 * np.pi), 0, None)
    pm25 = np.clip(10 + 30 * np.sin((hours.hour - 10) / 24 * 2 * np.pi), 5, 120)
    return pd.DataFrame(
        {"time": hours, "temp_c": temp, "rh": rh, "wind_ms": wind, "swdown": glob_rad, "pm25": pm25}
    )
