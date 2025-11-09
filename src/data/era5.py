import logging
from calendar import monthrange
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from ..config import AWS_REGION
from .demo import synthetic_hourly_series

try:
    import xarray as xr  # type: ignore
    import s3fs  # type: ignore
except Exception:  # pragma: no cover - fallback handled in fetch_era5_hourly
    xr = None
    s3fs = None

LOGGER = logging.getLogger(__name__)

ERA5_BUCKET = "nsf-ncar-era5"
ANALYSIS_PREFIX = "e5.oper.an.sfc"
MEAN_FLUX_PREFIX = "e5.oper.fc.sfc.meanflux"
MEAN_FLUX_CODE = "235_035_msdwswrf"
MEAN_FLUX_VAR = "MSDWSWRF"

ANALYSIS_FIELDS: Dict[str, Tuple[str, str]] = {
    "temp_k": ("128_167_2t", "VAR_2T"),
    "dew_k": ("128_168_2d", "VAR_2D"),
    "u10": ("128_165_10u", "VAR_10U"),
    "v10": ("128_166_10v", "VAR_10V"),
}


def fetch_era5_hourly(lat: float, lon: float, date: str, force_demo: bool = False) -> pd.DataFrame:
    """
    Retrieve hourly meteorology for the given UTC date by sampling the nearest ERA5 grid cell.
    Falls back to the synthetic demo series if ASDI access is unavailable.
    """
    start = pd.Timestamp(date).floor("D")
    end = start + pd.Timedelta(hours=23)

    if force_demo:
        LOGGER.info("Demo mode: using synthetic meteorology")
        _df = synthetic_hourly_series(date)[["time", "temp_c", "rh", "wind_ms", "swdown"]]
        try:
            _df.attrs["met_source"] = "demo"
        except Exception:
            pass
        return _df
    if xr is None or s3fs is None:
        LOGGER.warning("xarray/s3fs not available; using synthetic meteorology.")
        _df = synthetic_hourly_series(date)[["time", "temp_c", "rh", "wind_ms", "swdown"]]
        try:
            _df.attrs["met_source"] = "demo"
        except Exception:
            pass
        return _df

    try:
        fs = _get_filesystem()
        lon_mod = _to_360(lon)
        analysis = _load_analysis_fields(fs, lat, lon_mod, start, end)
        swdown = _load_swdown_flux(fs, lat, lon_mod, start - pd.Timedelta(hours=12), end + pd.Timedelta(hours=12))
        df = analysis.copy()
        df["temp_c"] = df["temp_k"] - 273.15
        df["dew_c"] = df["dew_k"] - 273.15
        df["rh"] = _relative_humidity(df["temp_c"], df["dew_c"])
        df["wind_ms"] = np.hypot(df["u10"], df["v10"])
        df["swdown"] = (
            swdown.reindex(df.index)
            .interpolate(method="time")
            .bfill()
            .ffill()
        )
        final = df[["temp_c", "rh", "wind_ms", "swdown"]].copy()
        final.reset_index(inplace=True)
        final.rename(columns={"index": "time"}, inplace=True)
        try:
            final.attrs["met_source"] = "asdi-era5"
        except Exception:
            pass
        LOGGER.info("ERA5 fetched from S3 (ASDI) for lat=%.3f lon=%.3f on %s", lat, lon, date)
        return final
    except Exception as exc:  # pragma: no cover - network issues
        LOGGER.exception("ERA5 fetch failed; falling back to synthetic series: %s", exc)
        _df = synthetic_hourly_series(date)[["time", "temp_c", "rh", "wind_ms", "swdown"]]
        try:
            _df.attrs["met_source"] = "demo"
        except Exception:
            pass
        return _df


def _get_filesystem() -> "s3fs.S3FileSystem":
    return s3fs.S3FileSystem(
        anon=True,
        default_fill_cache=False,
        default_cache_type="none",
        client_kwargs={"region_name": AWS_REGION},
    )


def _analysis_path(var_code: str, year: int, month: int) -> str:
    last_day = monthrange(year, month)[1]
    start_stamp = f"{year}{month:02d}0100"
    end_stamp = f"{year}{month:02d}{last_day:02d}23"
    return (
        f"{ERA5_BUCKET}/{ANALYSIS_PREFIX}/{year}{month:02d}/"
        f"e5.oper.an.sfc.{var_code}.ll025sc.{start_stamp}_{end_stamp}.nc"
    )


def _load_analysis_fields(
    fs: "s3fs.S3FileSystem", lat: float, lon: float, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    """Load the required analysis variables (T2M, D2M, U10, V10) for the target window."""
    year = start.year
    month = start.month
    data_frames = []
    for field_name, (code, var_name) in ANALYSIS_FIELDS.items():
        path = _analysis_path(code, year, month)
        series = _read_analysis_series(fs, path, var_name, lat, lon, start, end)
        data_frames.append(series.rename(field_name))
    df = pd.concat(data_frames, axis=1)
    df.index.name = "time"
    return df


def _read_analysis_series(
    fs: "s3fs.S3FileSystem",
    path: str,
    var_name: str,
    lat: float,
    lon: float,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    with fs.open(path, "rb") as fh:
        ds = xr.open_dataset(fh, engine="h5netcdf")
        try:
            arr = (
                ds[var_name]
                .sel(latitude=lat, longitude=lon, method="nearest")
                .sel(time=slice(start.to_pydatetime(), end.to_pydatetime()))
            )
            series = arr.to_series()
        finally:
            ds.close()
    return series


def _load_swdown_flux(
    fs: "s3fs.S3FileSystem", lat: float, lon: float, start: pd.Timestamp, end: pd.Timestamp
) -> pd.Series:
    """Load mean shortwave flux and convert to an hourly series covering [start, end]."""
    month_keys = _flux_months_for_range(start, end)
    paths = []
    for year, month in month_keys:
        paths.extend(_mean_flux_paths(year, month))
    seen = set()
    series_list: List[pd.Series] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        try:
            series = _read_flux_series(fs, path, lat, lon)
            series_list.append(series)
        except FileNotFoundError:
            LOGGER.warning("ERA5 mean flux file missing: %s", path)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("Failed to read %s: %s", path, exc)
    if not series_list:
        raise RuntimeError("No mean flux series were loaded.")
    merged = pd.concat(series_list).sort_index()
    merged = merged[~merged.index.duplicated(keep="last")]
    window = merged.loc[(merged.index >= start) & (merged.index <= end)]
    if window.empty:
        raise RuntimeError("Mean flux window is empty after filtering.")
    return window


def _read_flux_series(fs: "s3fs.S3FileSystem", path: str, lat: float, lon: float) -> pd.Series:
    with fs.open(path, "rb") as fh:
        ds = xr.open_dataset(fh, engine="h5netcdf")
        try:
            da = ds[MEAN_FLUX_VAR].sel(latitude=lat, longitude=lon, method="nearest")
            init_times = pd.to_datetime(ds["forecast_initial_time"].values)
            forecast_hours = ds["forecast_hour"].values.astype(int)
            values: List[float] = []
            times: List[pd.Timestamp] = []
            for idx, t0 in enumerate(init_times):
                row = da.isel(forecast_initial_time=idx).values
                for hour, val in zip(forecast_hours, row):
                    times.append(t0 + pd.Timedelta(hours=int(hour)))
                    values.append(float(val))
        finally:
            ds.close()
    return pd.Series(values, index=pd.DatetimeIndex(times, name="time"))


def _flux_months_for_range(start: pd.Timestamp, end: pd.Timestamp) -> Sequence[Tuple[int, int]]:
    points = [start, end, start - pd.Timedelta(days=1), end + pd.Timedelta(days=1)]
    months = {(p.year, p.month) for p in points}
    return sorted(months)


def _mean_flux_paths(year: int, month: int) -> List[str]:
    year_next, month_next = _increment_month(year, month)
    first = f"{year}{month:02d}0106"
    mid = f"{year}{month:02d}1606"
    next_stamp = f"{year_next}{month_next:02d}0106"
    base = f"{ERA5_BUCKET}/{MEAN_FLUX_PREFIX}/{year}{month:02d}"
    return [
        f"{base}/e5.oper.fc.sfc.meanflux.{MEAN_FLUX_CODE}.ll025sc.{first}_{mid}.nc",
        f"{base}/e5.oper.fc.sfc.meanflux.{MEAN_FLUX_CODE}.ll025sc.{mid}_{next_stamp}.nc",
    ]


def _increment_month(year: int, month: int) -> Tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _to_360(lon: float) -> float:
    return float((lon + 360.0) % 360.0)


def _relative_humidity(temp_c: pd.Series, dew_c: pd.Series) -> pd.Series:
    a, b = 17.625, 243.04
    alpha = (a * dew_c) / (b + dew_c)
    beta = (a * temp_c) / (b + temp_c)
    rh = np.clip(np.exp(alpha - beta), 0.0, 1.2)
    return rh.clip(0.0, 1.0)
