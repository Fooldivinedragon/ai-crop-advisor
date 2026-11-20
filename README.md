# AgroGuide

AI Powered Smart Crop Recommendation System: crop recommendation, weather-aware yield prediction and fertilizer advisory.
Final year B.Tech project, Department of CSE, The NorthCap University, Gurugram (2026–27).

A farmer enters soil N, P, K, pH, a location and a planting date. The website works out the season,
fetches five years of local weather from NASA POWER, recommends crops with a Random Forest model,
estimates yield in quintals per acre, prepares a fertilizer plan and explains the report in nine
Indian languages using an LLM (Gemini or Claude).

## Run locally

```bash
pip install -r requirements.txt
python train_model.py          # creates models/
cp .env.example .env           # then add your GEMINI_API_KEY
python app.py                  # http://127.0.0.1:5000
```

## Deploy on Render (free)

1. Push this folder to a GitHub repository.
2. On render.com choose **New > Blueprint**, select the repository; `render.yaml` sets everything up.
3. When asked, enter your `GEMINI_API_KEY`.

The free plan sleeps after about 15 minutes without visitors; the first visit afterwards takes
about a minute to load.

## Project structure

| Path | Purpose |
|---|---|
| `app.py` | Flask website and API (`/api/predict`, `/api/explain`) |
| `pipeline.py` | End-to-end advisory flow |
| `location.py`, `weather.py`, `crop_calendar.py` | Location, NASA POWER weather, seasons and crop data |
| `recommender.py`, `train_model.py` | Random Forest crop model |
| `yield_model.py`, `fertilizer.py` | Yield estimate and fertilizer plan |
| `explain.py` | LLM explanation in nine languages |
| `add_wheat_data.py` | Builds the wheat training rows from NASA POWER weather |
| `templates/`, `static/` | Website pages, styles and images |
