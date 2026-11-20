"""
train_model.py
==============
Trains the crop recommendation model on Crop_recommendation_cleaned.csv
plus the wheat rows from wheat_generated.csv (see add_wheat_data.py) and
saves the artifacts used by the app (model, scaler, label encoder,
meta). Hyperparameters are the best ones found by the RandomizedSearchCV
run in AI_croprecommendation_system.ipynb.
"""

import json
import os

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "Crop_recommendation_cleaned.csv")
EXTRA_DATA = [os.path.join(BASE_DIR, "wheat_generated.csv")]
MODEL_DIR = os.path.join(BASE_DIR, "models")
FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
TARGET = "label"
RANDOM_STATE = 42


def main():
    df = pd.concat([pd.read_csv(p) for p in [DATA_PATH, *EXTRA_DATA]], ignore_index=True)
    print(f"Training on {len(df)} rows, {df[TARGET].nunique()} crops")
    X = df[FEATURES].values
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(df[TARGET].values)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    params = dict(n_estimators=200, min_samples_split=5, min_samples_leaf=1,
                  max_features="log2", max_depth=None)
    model = RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1, **params)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"Random Forest test accuracy: {acc:.4f}")
    wheat = label_encoder.transform(["wheat"])[0]
    mask = y_test == wheat
    print(f"Wheat test accuracy: {accuracy_score(y_test[mask], y_pred[mask]):.4f} ({mask.sum()} rows)")

    # Refit on all data for deployment
    model.fit(scaler.transform(X), y)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, os.path.join(MODEL_DIR, "crop_model.pkl"))
    joblib.dump(scaler, os.path.join(MODEL_DIR, "scaler.pkl"))
    joblib.dump(label_encoder, os.path.join(MODEL_DIR, "label_encoder.pkl"))

    # Per-crop soil profile (used by the yield model as the "ideal" soil)
    soil = df.groupby(TARGET).agg(
        N=("N", "median"), P=("P", "median"), K=("K", "median"),
        ph_low=("ph", lambda s: s.quantile(0.05)), ph_high=("ph", lambda s: s.quantile(0.95)),
    ).round(2)

    meta = {
        "features": FEATURES,
        "classes": label_encoder.classes_.tolist(),
        "best_model_name": "random_forest",
        "best_model_params": params,
        "test_accuracy": acc,
        "soil_profiles": soil.to_dict(orient="index"),
    }
    with open(os.path.join(MODEL_DIR, "model_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Artifacts saved to {MODEL_DIR}")


if __name__ == "__main__":
    main()
