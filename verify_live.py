import argparse
import logging

from src.data.era5 import fetch_era5_hourly
from src.data.openaq import fetch_pm25_s3


def main():
    parser = argparse.ArgumentParser(description="Verify live ASDI/OpenAQ data access.")
    parser.add_argument("--lat", type=float, default=34.0522)
    parser.add_argument("--lon", type=float, default=-118.2437)
    parser.add_argument("--date", type=str, default="2024-07-01")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    lat, lon, date = args.lat, args.lon, args.date
    logging.info("Fetching ERA5 + OpenAQ for lat=%.4f lon=%.4f date=%s", lat, lon, date)
    met = fetch_era5_hourly(lat, lon, date, force_demo=False)
    print("ERA5 rows", len(met))
    print("met columns", met.columns.tolist())
    print("temp range", float(met["temp_c"].min()), float(met["temp_c"].max()))
    print("swdown max", float(met["swdown"].max()))
    print("met source attr", getattr(met, "attrs", {}).get("met_source"))

    pm = fetch_pm25_s3(lat, lon, date)
    if pm is not None and not pm.empty:
        print("OpenAQ rows", len(pm))
        print("pm range", float(pm["pm25"].min()), float(pm["pm25"].max()))
        print("aq source attr", getattr(pm, "attrs", {}).get("aq_source"))
    else:
        print("OpenAQ rows 0 (fallback)")


if __name__ == "__main__":
    main()
