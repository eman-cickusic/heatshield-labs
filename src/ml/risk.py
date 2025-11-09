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
    return {"hours_by_tier": counts, "peak_wbgt_c": peak}
