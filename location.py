"""
location.py
===========
Resolves a farmer's location to latitude / longitude.

Accepts either GPS coordinates directly or a district name. Common
districts are looked up in a built-in table; anything else is geocoded
with the free Open-Meteo geocoding API (restricted to India).
"""

import requests

# District headquarters (lat, lon)
DISTRICTS = {
    "ludhiana": (30.90, 75.85),
    "amritsar": (31.63, 74.87),
    "patiala": (30.34, 76.39),
    "bathinda": (30.21, 74.95),
    "karnal": (29.69, 76.99),
    "hisar": (29.15, 75.72),
    "meerut": (28.98, 77.71),
    "agra": (27.18, 78.01),
    "lucknow": (26.85, 80.95),
    "kanpur": (26.45, 80.33),
    "varanasi": (25.32, 82.97),
    "gorakhpur": (26.76, 83.37),
    "patna": (25.59, 85.14),
    "gaya": (24.79, 85.00),
    "jaipur": (26.91, 75.79),
    "jodhpur": (26.24, 73.02),
    "bikaner": (28.02, 73.31),
    "kota": (25.21, 75.86),
    "bhopal": (23.26, 77.41),
    "indore": (22.72, 75.86),
    "jabalpur": (23.18, 79.99),
    "raipur": (21.25, 81.63),
    "nagpur": (21.15, 79.09),
    "pune": (18.52, 73.86),
    "nashik": (20.00, 73.79),
    "aurangabad": (19.88, 75.34),
    "solapur": (17.66, 75.91),
    "ahmedabad": (23.02, 72.57),
    "rajkot": (22.30, 70.80),
    "surat": (21.17, 72.83),
    "kolkata": (22.57, 88.36),
    "bardhaman": (23.23, 87.86),
    "cuttack": (20.46, 85.88),
    "guwahati": (26.14, 91.74),
    "ranchi": (23.34, 85.31),
    "hyderabad": (17.39, 78.49),
    "warangal": (17.97, 79.59),
    "guntur": (16.31, 80.44),
    "bengaluru": (12.97, 77.59),
    "mysuru": (12.30, 76.64),
    "belagavi": (15.85, 74.50),
    "chennai": (13.08, 80.27),
    "coimbatore": (11.02, 76.96),
    "thanjavur": (10.79, 79.14),
    "madurai": (9.93, 78.12),
    "thiruvananthapuram": (8.52, 76.94),
    "kozhikode": (11.26, 75.78),
    "shimla": (31.10, 77.17),
    "srinagar": (34.08, 74.80),
    "dehradun": (30.32, 78.03),
}

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


class LocationError(ValueError):
    pass


def resolve_location(district: str = None, lat: float = None, lon: float = None) -> dict:
    """Return {"name", "lat", "lon", "source"} for a district name or GPS point."""
    if lat is not None and lon is not None:
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise LocationError("Latitude/longitude out of range")
        return {"name": district or f"{lat:.3f}, {lon:.3f}", "lat": lat, "lon": lon, "source": "gps"}

    if not district:
        raise LocationError("Provide a district name or GPS coordinates")

    key = district.strip().lower()
    if key in DISTRICTS:
        lat, lon = DISTRICTS[key]
        return {"name": district.strip().title(), "lat": lat, "lon": lon, "source": "district table"}

    try:
        resp = requests.get(
            GEOCODE_URL,
            params={"name": district.strip(), "count": 1, "countryCode": "IN", "format": "json"},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except requests.RequestException as exc:
        raise LocationError(f"Could not look up '{district}': {exc}") from exc

    if not results:
        raise LocationError(f"Unknown district '{district}'. Try a nearby city or use GPS.")
    hit = results[0]
    name = ", ".join(p for p in (hit.get("name"), hit.get("admin1")) if p)
    return {"name": name, "lat": hit["latitude"], "lon": hit["longitude"], "source": "geocoded"}
