from typing import Tuple


def round_latlon(lat: float, lon: float, ndigits: int = 3) -> Tuple[float, float]:
    return (round(float(lat), ndigits), round(float(lon), ndigits))
