import pandas as pd
import numpy as np
from .wbgt import wbgt_liljegren_from_met, risk_tiers


def compute_risk(hourly_met: pd.DataFrame) -> pd.DataFrame:
    df = hourly_met.copy()
    df["wbgt_c"] = wbgt_liljegren_from_met(
        df["temp_c"].values,
        df["rh"].values,
        df["swdown"].values,
        df["wind_ms"].values,
    )
    if "pm25" not in df.columns:
        df["pm25"] = 10.0
    df["tier"] = risk_tiers(df["wbgt_c"].values, df["pm25"].values)
    return df


def summarize_day(df: pd.DataFrame) -> dict:
    counts = df["tier"].value_counts().to_dict()
    peak = float(df["wbgt_c"].max())
    hottest_time = None
    if "time" in df.columns:
        hottest_row = df.loc[df["wbgt_c"].idxmax()]
        try:
            hottest_time = pd.to_datetime(hottest_row["time"]).isoformat()
        except Exception:
            hottest_time = str(hottest_row["time"])
    orange_red_hours = int(df[df["tier"].isin(["orange", "red"])].shape[0])
    pm_peak = float(df["pm25"].max()) if "pm25" in df.columns else None
    pm_alert = pm_peak is not None and pm_peak >= 55.0
    avg_wind = float(df["wind_ms"].mean()) if "wind_ms" in df.columns else None
    median_rh = float(df["rh"].median()) if "rh" in df.columns else None
    return {
        "hours_by_tier": counts,
        "peak_wbgt_c": peak,
        "hottest_time": hottest_time,
        "orange_red_hours": orange_red_hours,
        "pm_peak": pm_peak,
        "pm_alert": pm_alert,
        "avg_wind": avg_wind,
        "median_rh": median_rh,
    }
