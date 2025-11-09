import numpy as np
import pandas as pd
import os

# Approximate outdoor WBGT in shade using Stull-like approximation
# For scientifically rigorous WBGT, implement Liljegren; this is sufficient for MVP ranking.


def dewpoint_c(temp_c: float, rh: float) -> float:
    # Magnus-Tetens approximation
    a, b = 17.625, 243.04
    gamma = np.log(rh) + (a * temp_c) / (b + temp_c)
    return (b * gamma) / (a - gamma)


def wbgt_from_met(
    temp_c: np.ndarray, rh: np.ndarray, glob_rad: np.ndarray, wind_ms: np.ndarray
) -> np.ndarray:
    # crude globe temp proxy via shortwave;
    tg = temp_c + 0.02 * glob_rad / (wind_ms + 1e-6)
    # natural wet-bulb approximation
    tw = (
        temp_c * np.arctan(0.151977 * np.sqrt(rh * 100 + 8.313659))
        + np.arctan(temp_c + rh)
        - np.arctan(rh - 1.676331)
        + 0.00391838 * (rh) ** (3 / 2) * np.arctan(0.023101 * rh)
        - 4.686035
    )
    # final WBGT (outdoor, shade)
    wbgt = 0.7 * tw + 0.2 * tg + 0.1 * temp_c
    return wbgt


def wbgt_liljegren_from_met(
    temp_c: np.ndarray,
    rh: np.ndarray,
    swdown: np.ndarray,
    wind_ms: np.ndarray,
    p_hPa: float = 1013.0,
) -> np.ndarray:
    """
    Simplified Liljegren-style WBGT approximation suitable for outdoor shade.
    Trends: ↑solar, ↑humidity, ↑temp ⇒ ↑WBGT; ↑wind ⇒ ↓WBGT.

    Notes:
    - Uses Stull wet-bulb approximation for natural wet-bulb (Tw).
    - Approximates globe temperature (Tg) from shortwave and wind.
    - p_hPa reserved for future pressure dependence.
    """
    t = np.asarray(temp_c, dtype=float)
    rh_in = np.asarray(rh, dtype=float)
    rh01 = np.clip(rh_in, 0.0, 1.0)
    rh_pct = 100.0 * rh01
    sw = np.maximum(np.asarray(swdown, dtype=float), 0.0)
    u = np.maximum(np.asarray(wind_ms, dtype=float), 0.0)

    # Stull (2011) wet-bulb approximation; robust and monotonic in RH and T
    tw = (
        t * np.arctan(0.151977 * np.sqrt(rh_pct + 8.313659))
        + np.arctan(t + rh_pct)
        - np.arctan(rh_pct - 1.676331)
        + 0.00391838 * (rh_pct**1.5) * np.arctan(0.023101 * rh_pct)
        - 4.686035
    )

    # Approximate globe temperature from shortwave and ventilation
    # Scale SW to degrees C using a gentle factor and dampen with wind
    tg = t + (0.012 * sw) / (1.0 + 0.5 * u + 1e-6)

    wbgt = 0.7 * tw + 0.2 * tg + 0.1 * t
    return wbgt


def _wbgt_thresholds_from_env() -> tuple[float, float, float]:
    raw = os.getenv("WBGT_THRESH", "27,30,32")
    try:
        parts = [float(x.strip()) for x in raw.split(",") if x.strip()]
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
    except Exception:
        pass
    return 27.0, 30.0, 32.0


def risk_tiers(wbgt_c: np.ndarray, pm25: np.ndarray) -> pd.Series:
    # Simple thresholds for demo (customize to your policy region)
    # WBGT (C): <27 green, 27-30 yellow, 30-32 orange, >32 red
    # PM2.5 (µg/m3): <12 good, 12-35 moderate, 35-55 unhealthy-sens, >55 unhealthy
    t1, t2, t3 = _wbgt_thresholds_from_env()
    wb = pd.cut(
        wbgt_c,
        bins=[-100, t1, t2, t3, 100],
        labels=["green", "yellow", "orange", "red"],
        right=False,
    )
    pm = pd.cut(
        pm25,
        bins=[-1, 12, 35, 55, 1e6],
        labels=["good", "moderate", "unhealthy-sens", "unhealthy"],
        right=False,
    )
    # combine: worst of the two
    tier_order = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
    pm_map = {"good": 0, "moderate": 1, "unhealthy-sens": 2, "unhealthy": 3}
    wb_codes = pd.Series(wb).map(tier_order).astype(int).values
    pm_codes = pd.Series(pm).map(pm_map).astype(int).values
    worst = np.maximum(wb_codes, pm_codes)
    inv = {v: k for k, v in tier_order.items()}
    return pd.Series(worst).map(inv)
