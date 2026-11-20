"""
weather.py
==========
Historical weather for a location from NASA POWER, aggregated over a
crop-growing window that starts on the planting date.

The same calendar window (e.g. 15 Nov + 120 days) is taken from each of
the last N complete years, giving the "typical" weather a crop planted on
that date would experience, plus the year-to-year spread.
"""

import json
import os
from datetime import date, timedelta

import pandas as pd
import requests

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETERS = {
    "T2M": "temp",                    # deg C, daily mean
    "PRECTOTCORR": "rain",            # mm/day
    "RH2M": "humidity",               # %
    "ALLSKY_SFC_SW_DWN": "solar",     # MJ/m^2/day
}
HISTORY_YEARS = 5
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")


class WeatherError(RuntimeError):
    pass


def _history_range(today: date, years: int):
    """Daily data range covering `years`+1 full past years plus the following
    year's first half, so a window starting late in the last year still fits.
    NASA POWER lags real time by a few days, hence the safety margin."""
    last_full_year = today.year - 1
    start = date(last_full_year - years, 1, 1)
    end = min(date(last_full_year + 1, 12, 31), today - timedelta(days=10))
    return start, end


def fetch_daily(lat: float, lon: float, start: date, end: date) -> pd.DataFrame:
    """Daily NASA POWER data as a DataFrame indexed by date (cached on disk)."""
    lat, lon = round(lat, 2), round(lon, 2)
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"power_{lat}_{lon}_{start:%Y%m%d}_{end:%Y%m%d}.json")

    if os.path.exists(cache_file):
        with open(cache_file) as f:
            payload = json.load(f)
    else:
        try:
            resp = requests.get(
                POWER_URL,
                params={
                    "parameters": ",".join(PARAMETERS),
                    "community": "AG",
                    "latitude": lat,
                    "longitude": lon,
                    "start": f"{start:%Y%m%d}",
                    "end": f"{end:%Y%m%d}",
                    "format": "JSON",
                },
                timeout=60,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as exc:
            raise WeatherError(f"NASA POWER request failed: {exc}") from exc
        with open(cache_file, "w") as f:
            json.dump(payload, f)

    params = payload["properties"]["parameter"]
    df = pd.DataFrame({PARAMETERS[k]: params[k] for k in PARAMETERS})
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    fill = payload.get("header", {}).get("fill_value", -999.0)
    return df.replace(fill, float("nan"))


def _window_features(df: pd.DataFrame) -> dict:
    days = len(df)
    total_rain = float(df["rain"].sum())
    return {
        "avg_temp": round(float(df["temp"].mean()), 2),
        "min_temp": round(float(df["temp"].min()), 2),
        "max_temp": round(float(df["temp"].max()), 2),
        "total_rainfall": round(total_rain, 1),
        # Mean rainfall per 30 days - the scale the recommendation dataset uses
        "monthly_rainfall": round(total_rain / days * 30, 1),
        "avg_humidity": round(float(df["humidity"].mean()), 2),
        "avg_solar": round(float(df["solar"].mean()), 2),
    }


def growing_period_weather(lat: float, lon: float, planting_date: date, days: int,
                           years: int = HISTORY_YEARS, today: date = None) -> dict:
    """Weather features for `days` days after `planting_date`, averaged over
    the last `years` years that have complete data for that window."""
    today = today or date.today()
    start, end = _history_range(today, years)
    daily = fetch_daily(lat, lon, start, end)

    per_year = []
    for year in range(today.year - 1, start.year - 1, -1):
        try:
            w_start = planting_date.replace(year=year)
        except ValueError:  # 29 Feb in a non-leap year
            w_start = date(year, 3, 1)
        w_end = w_start + timedelta(days=days - 1)
        if w_end > end:
            continue
        window = daily.loc[pd.Timestamp(w_start):pd.Timestamp(w_end)].dropna()
        if len(window) < days * 0.9:
            continue
        per_year.append({"year": year, **_window_features(window)})
        if len(per_year) == years:
            break

    if not per_year:
        raise WeatherError("No complete historical weather for this window")

    keys = [k for k in per_year[0] if k != "year"]
    mean = {k: round(sum(y[k] for y in per_year) / len(per_year), 2) for k in keys}
    return {
        "window_start": f"{planting_date:%d %b}",
        "window_end": f"{planting_date + timedelta(days=days - 1):%d %b}",
        "days": days,
        "years": [y["year"] for y in per_year],
        "mean": mean,
        "per_year": per_year,
    }
