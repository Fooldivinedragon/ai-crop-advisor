"""
pipeline.py
===========
End-to-end flow. The farmer gives soil N, P, K, pH, a location and a
planting date; the system works out everything else:

  1. location        -> lat / lon
  2. planting date   -> likely season
  3. NASA POWER      -> typical weather for the season window
  4. ML model        -> candidate crops (in-season crops first)
  5. per crop        -> growing period -> its own weather window
  6. yield model     -> expected yield + range + limiting factors
  7. re-rank         -> model probability x climate suitability -> top 3
  8. fertilizer      -> soil status + dose, products and schedule per crop
"""

from datetime import date, timedelta

from crop_calendar import CROPS, DEFAULT_WINDOW_DAYS, SEASON_INFO, season_for_date
from fertilizer import fertilizer_plan
from location import resolve_location
from recommender import CropRecommender
from weather import growing_period_weather
from yield_model import predict_yield

# Crops from the ML model that are checked against the local climate
CANDIDATES = 6
# Crops the model gives less than this probability are not shown
MIN_PROBABILITY = 0.01

_recommender = None


def get_recommender() -> CropRecommender:
    global _recommender
    if _recommender is None:
        _recommender = CropRecommender()
    return _recommender


def run(N: float, P: float, K: float, ph: float, planting_date: date,
        district: str = None, lat: float = None, lon: float = None,
        irrigated: bool = True) -> dict:
    soil = {"N": N, "P": P, "K": K, "ph": ph}
    recommender = get_recommender()

    location = resolve_location(district, lat, lon)
    season = season_for_date(planting_date)

    season_weather = growing_period_weather(
        location["lat"], location["lon"], planting_date, DEFAULT_WINDOW_DAYS
    )
    candidates = recommender.top_crops(soil, season_weather["mean"], season, k=CANDIDATES)

    crops = []
    for rec in candidates:
        crop = rec["crop"]
        days = CROPS[crop]["growing_days"]
        crop_weather = growing_period_weather(location["lat"], location["lon"], planting_date, days)
        crops.append({
            **rec,
            "sowing_seasons": CROPS[crop]["seasons"],
            "growing_days": days,
            "expected_harvest": f"{planting_date + timedelta(days=days):%d %b %Y}",
            "weather": crop_weather,
            "yield": predict_yield(crop, soil, crop_weather, recommender.soil_profiles[crop], irrigated),
        })
        crops[-1]["score"] = round(rec["probability"] * crops[-1]["yield"]["climate_suitability"], 4)

    crops.sort(key=lambda c: (c["fits_season"], c["score"]), reverse=True)
    # Keep at least one crop even if the model is unsure about everything
    crops = [c for i, c in enumerate(crops) if i == 0 or c["probability"] >= MIN_PROBABILITY][:3]
    for c in crops:
        c["fertilizer"] = fertilizer_plan(c["crop"], soil, recommender.soil_profiles[c["crop"]], planting_date)

    return {
        "inputs": {**soil, "planting_date": planting_date.isoformat(), "irrigated": irrigated},
        "location": location,
        "season": {"name": season, "description": SEASON_INFO[season]},
        "season_weather": season_weather,
        "top_crops": crops,
    }


if __name__ == "__main__":
    import json

    result = run(N=90, P=42, K=43, ph=6.5, planting_date=date(2026, 11, 15), district="Ludhiana")
    for c in result["top_crops"]:
        c["weather"].pop("per_year")
    print(json.dumps(result, indent=2))
