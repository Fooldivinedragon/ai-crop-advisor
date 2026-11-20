"""
recommender.py
==============
Wraps the trained crop recommendation model. Weather inputs come from
NASA POWER instead of the farmer, and crops that cannot be sown in the
current season are pushed below season-compatible ones.
"""

import json
import os

import joblib
import numpy as np

from crop_calendar import crop_fits_season

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


class CropRecommender:
    def __init__(self, model_dir: str = MODEL_DIR):
        self.model = joblib.load(os.path.join(model_dir, "crop_model.pkl"))
        self.scaler = joblib.load(os.path.join(model_dir, "scaler.pkl"))
        self.label_encoder = joblib.load(os.path.join(model_dir, "label_encoder.pkl"))
        with open(os.path.join(model_dir, "model_meta.json")) as f:
            self.meta = json.load(f)

    @property
    def soil_profiles(self) -> dict:
        return self.meta["soil_profiles"]

    def top_crops(self, soil: dict, weather_mean: dict, season: str, k: int = 3) -> list:
        """Top-k crops for soil + typical weather, preferring in-season crops."""
        row = np.array([[
            soil["N"], soil["P"], soil["K"],
            weather_mean["avg_temp"],
            weather_mean["avg_humidity"],
            soil["ph"],
            weather_mean["monthly_rainfall"],
        ]])
        probs = self.model.predict_proba(self.scaler.transform(row))[0]
        classes = self.label_encoder.inverse_transform(self.model.classes_)

        ranked = sorted(
            (
                {"crop": str(c), "probability": float(p), "fits_season": crop_fits_season(str(c), season)}
                for c, p in zip(classes, probs)
            ),
            key=lambda r: (r["fits_season"], r["probability"]),
            reverse=True,
        )
        return ranked[:k]
