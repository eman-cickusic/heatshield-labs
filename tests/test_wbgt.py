import os
import numpy as np
import pandas as pd

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from ml.wbgt import wbgt_liljegren_from_met


def test_wbgt_monotonic_temperature():
    n = 24
    base_t = np.full(n, 30.0)
    base_rh = np.full(n, 0.5)
    base_sw = np.linspace(0, 800, n)
    base_u = np.full(n, 2.0)

    w0 = wbgt_liljegren_from_met(base_t, base_rh, base_sw, base_u)
    w1 = wbgt_liljegren_from_met(base_t + 2.0, base_rh, base_sw, base_u)
    diff = w1 - w0
    assert float(diff.min()) > 0.0


def test_wbgt_monotonic_humidity_and_solar_and_wind():
    n = 24
    t = np.full(n, 32.0)
    rh_low = np.full(n, 0.3)
    rh_high = np.full(n, 0.7)
    sw_low = np.zeros(n)
    sw_high = np.full(n, 900.0)
    u_low = np.full(n, 0.5)
    u_high = np.full(n, 5.0)

    w_rh_low = wbgt_liljegren_from_met(t, rh_low, sw_low, u_low)
    w_rh_high = wbgt_liljegren_from_met(t, rh_high, sw_low, u_low)
    assert float((w_rh_high - w_rh_low).min()) > 0.0

    w_sw_low = wbgt_liljegren_from_met(t, rh_low, sw_low, u_low)
    w_sw_high = wbgt_liljegren_from_met(t, rh_low, sw_high, u_low)
    assert float((w_sw_high - w_sw_low).min()) > 0.0

    w_u_low = wbgt_liljegren_from_met(t, rh_low, sw_high, u_low)
    w_u_high = wbgt_liljegren_from_met(t, rh_low, sw_high, u_high)
    # Higher wind should reduce WBGT
    assert float((w_u_low - w_u_high).min()) > 0.0


def test_wbgt_hot_humid_high_solar_exceeds_threshold():
    n = 24
    t = np.full(n, 35.0)
    rh = np.full(n, 0.75)
    sw = np.full(n, 950.0)
    wind = np.full(n, 0.8)

    wbgt = wbgt_liljegren_from_met(t, rh, sw, wind)
    assert float(wbgt.mean()) > 30.0
    assert float(wbgt.max()) > 32.0
