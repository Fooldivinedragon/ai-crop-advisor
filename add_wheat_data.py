"""
add_wheat_data.py
=================
The Kaggle crop recommendation dataset has no wheat. This script builds
100 wheat rows in the same format (N, P, K, temperature, humidity, ph,
rainfall, label) and saves them to wheat_generated.csv, which
train_model.py adds to the training data.

  - Weather columns are REAL: NASA POWER data for major wheat-growing
    districts, wheat sowing dates (1 Nov - 10 Dec) and recent years,
    aggregated exactly the way the app does at prediction time
    (120-day window from planting: mean temperature, mean humidity,
    rainfall per 30 days).
  - Soil columns (N, P, K, pH) are sampled from ranges typical for wheat,
    on the same scale as the rest of the dataset, like the original
    dataset's own rows.

Run once (needs internet the first time; responses are cached):
    python add_wheat_data.py
"""

import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

from crop_calendar import DEFAULT_WINDOW_DAYS
from location import DISTRICTS
from weather import growing_period_weather

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(BASE_DIR, "wheat_generated.csv")
ROWS = 100
RANDOM_STATE = 42

# Main wheat-growing districts (Punjab, Haryana, UP, Bihar, Rajasthan, MP)
WHEAT_DISTRICTS = [
    "ludhiana", "amritsar", "patiala", "bathinda", "karnal", "hisar",
    "meerut", "agra", "kanpur", "lucknow", "varanasi", "gorakhpur",
    "patna", "jaipur", "kota", "bhopal", "indore", "jabalpur",
]

# Soil ranges for wheat on the dataset's scale
SOIL_RANGES = {"N": (80, 120), "P": (35, 65), "K": (30, 50), "ph": (6.0, 8.2)}


def weather_samples() -> list:
    """One weather record per (district, sowing date, year) combination."""
    samples = []
    sowing_dates = [date(2026, 11, 1) + timedelta(days=d) for d in range(0, 41, 10)]
    for name in WHEAT_DISTRICTS:
        lat, lon = DISTRICTS[name]
        for sow in sowing_dates:
            w = growing_period_weather(lat, lon, sow, DEFAULT_WINDOW_DAYS)
            for yr in w["per_year"]:
                samples.append({
                    "temperature": yr["avg_temp"],
                    "humidity": yr["avg_humidity"],
                    "rainfall": yr["monthly_rainfall"],
                })
        print(f"  {name}: done")
    return samples


def main():
    rng = np.random.default_rng(RANDOM_STATE)
    print("Fetching NASA POWER weather for wheat districts...")
    samples = weather_samples()
    picks = rng.choice(len(samples), size=ROWS, replace=False)

    rows = []
    for i in picks:
        w = samples[i]
        rows.append({
            "N": int(rng.integers(*SOIL_RANGES["N"], endpoint=True)),
            "P": int(rng.integers(*SOIL_RANGES["P"], endpoint=True)),
            "K": int(rng.integers(*SOIL_RANGES["K"], endpoint=True)),
            "temperature": w["temperature"],
            "humidity": w["humidity"],
            "ph": round(float(rng.uniform(*SOIL_RANGES["ph"])), 3),
            "rainfall": w["rainfall"],
            "label": "wheat",
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(df)} wheat rows to {OUT_PATH}")
    print(df.describe().round(1))


if __name__ == "__main__":
    main()
