import logging
import pandas as pd
import httpx
from typing import List

from ..config import OPENAQ_API_KEY

try:
    import s3fs  # type: ignore
except Exception:
    s3fs = None

# Minimal OpenAQ fetch using REST (for last 24h), fallback to demo if rate-limited
# For production, use S3 parquet via Athena/S3Select to stay fully on ASDI.

BASE = "https://api.openaq.org/v2/measurements"
LOGGER = logging.getLogger(__name__)


def _headers():
    return {"X-API-Key": OPENAQ_API_KEY} if OPENAQ_API_KEY else None


def fetch_pm25(lat: float, lon: float, date: str) -> pd.DataFrame:
    try:
        params = {
            "parameter": "pm25",
            "coordinates": f"{lat},{lon}",
            "date_from": f"{date}T00:00:00",
            "date_to": f"{date}T23:59:59",
            "radius": 25000,
            "limit": 1000,
            "sort": "asc",
        }
        r = httpx.get(BASE, params=params, timeout=20, headers=_headers())
        r.raise_for_status()
        items = r.json().get("results", [])
        if not items:
            return pd.DataFrame()
        df = pd.DataFrame(items)
        df["time"] = pd.to_datetime(df["date"].apply(lambda d: d.get("utc")))
        df = df[["time", "value"]].rename(columns={"value": "pm25"})
        try:
            df.attrs["aq_source"] = "openaq-rest"
        except Exception:
            pass
        LOGGER.info("OpenAQ REST returned %d rows near lat=%.3f lon=%.3f.", len(df), lat, lon)
        return df
    except Exception as exc:
        LOGGER.warning("OpenAQ REST request failed near lat=%.3f lon=%.3f: %s", lat, lon, exc)
        return pd.DataFrame()


def _nearest_location_ids(lat: float, lon: float, radius_m: int = 25000, limit: int = 3) -> List[int]:
    """Resolve nearest OpenAQ location IDs using v3 API.

    Tries semicolon and comma coordinate separators with minimal params.
    """
    headers = _headers()
    base_url = "https://api.openaq.org/v3/locations"
    attempts = [
        {"coordinates": f"{lat};{lon}", "radius": radius_m, "limit": limit, "order_by": "distance"},
        {"coordinates": f"{lat},{lon}", "radius": radius_m, "limit": limit, "order_by": "distance"},
    ]
    for params in attempts:
        try:
            r = httpx.get(base_url, params=params, headers=headers, timeout=20)
            r.raise_for_status()
            items = r.json().get("results", [])
            ids = [int(it.get("id")) for it in items if it.get("id") is not None]
            if ids:
                return ids
        except httpx.HTTPStatusError as exc:
            LOGGER.warning("OpenAQ locations attempt failed (%s): %s", exc.response.status_code, exc)
        except Exception as exc:
            LOGGER.warning("OpenAQ locations attempt error: %s", exc)
    return []


def fetch_pm25_s3(lat: float, lon: float, date: str) -> pd.DataFrame:
    """Attempt to read hourly PM2.5 for the given day from the OpenAQ S3 archive.
    Falls back to empty DataFrame if not available.
    """
    if s3fs is None:
        LOGGER.warning("s3fs not available; cannot read OpenAQ S3 archive.")
        return pd.DataFrame()
    year = pd.Timestamp(date).year
    month = pd.Timestamp(date).month
    day = pd.Timestamp(date).day
    ymd = f"{year}{month:02d}{day:02d}"
    ids = _nearest_location_ids(lat, lon)
    if not ids:
        LOGGER.info("No OpenAQ location IDs found within search radius near lat=%.3f lon=%.3f.", lat, lon)
        return pd.DataFrame()
    fs = s3fs.S3FileSystem(anon=True)
    for loc_id in ids:
        path = (
            f"openaq-data-archive/records/csv.gz/locationid={loc_id}/year={year}/month={month:02d}/"
            f"location-{loc_id}-{ymd}.csv.gz"
        )
        try:
            with fs.open(path, "rb") as f:
                df = pd.read_csv(f, compression="gzip")
            df = df[df["parameter"] == "pm25"][ ["datetime", "value"] ].copy()
            if df.empty:
                continue
            df["time"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_convert(None)
            ser = df.set_index("time")["value"].astype(float).resample("h").mean().interpolate()
            out = ser.reset_index().rename(columns={"value": "pm25"})
            try:
                out.attrs["aq_source"] = "openaq-s3"
            except Exception:
                pass
            LOGGER.info(
                "OpenAQ S3 fetched %d hourly rows for location_id=%s on %s.",
                len(out),
                loc_id,
                date,
            )
            return out
        except FileNotFoundError:
            continue
        except Exception as exc:
            LOGGER.warning("Failed reading OpenAQ S3 file %s: %s", path, exc)
            continue
    LOGGER.info("OpenAQ S3 had no PM2.5 files near lat=%.3f lon=%.3f on %s.", lat, lon, date)
    return pd.DataFrame()
