from datetime import datetime, timezone


def utc_today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
