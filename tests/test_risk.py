import os
import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from ml.wbgt import risk_tiers
from ml.risk import compute_risk, summarize_day


def test_risk_tier_edges_default_thresholds(monkeypatch):
    # Ensure default thresholds 27,30,32
    monkeypatch.delenv("WBGT_THRESH", raising=False)
    vals = np.array([26.9, 27.0, 29.9, 30.0, 31.9, 32.0])
    pm = np.full_like(vals, 10.0)
    tiers = list(risk_tiers(vals, pm))
    expected = ["green", "yellow", "yellow", "orange", "orange", "red"]
    assert tiers == expected


def test_risk_tier_env_thresholds(monkeypatch):
    monkeypatch.setenv("WBGT_THRESH", "28,31,33")
    vals = np.array([27.9, 28.0, 30.9, 31.0, 32.9, 33.0])
    pm = np.full_like(vals, 10.0)
    tiers = list(risk_tiers(vals, pm))
    expected = ["green", "yellow", "yellow", "orange", "orange", "red"]
    assert tiers == expected


def test_compute_risk_defaults_pm25_and_summary():
    times = pd.date_range("2024-07-01", periods=5, freq="h")
    hourly = pd.DataFrame(
        {
            "time": times,
            "temp_c": np.linspace(30, 34, len(times)),
            "rh": np.full(len(times), 0.6),
            "swdown": np.linspace(100, 900, len(times)),
            "wind_ms": np.full(len(times), 1.5),
        }
    )
    df = compute_risk(hourly)
    assert "wbgt_c" in df.columns
    assert "pm25" in df.columns
    assert float(df["pm25"].iloc[0]) == 10.0

    summary = summarize_day(df)
    assert "hours_by_tier" in summary
    total_hours = sum(summary["hours_by_tier"].values())
    assert total_hours == len(times)
