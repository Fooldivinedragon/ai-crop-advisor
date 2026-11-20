"""
location.py
===========
Resolves a farmer's location to latitude / longitude.

Accepts either GPS coordinates directly or a district name. Common
districts are looked up in a built-in table; anything else is geocoded
with the free Open-Meteo geocoding API (restricted to India).
"""

import re

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

# States and union territories, mapped to a representative farming district
# (or the capital): state -> (display name, representative place, lat, lon)
STATES = {
    "andhra pradesh": ("Andhra Pradesh", "Guntur", 16.31, 80.44),
    "arunachal pradesh": ("Arunachal Pradesh", "Itanagar", 27.08, 93.61),
    "assam": ("Assam", "Guwahati", 26.14, 91.74),
    "bihar": ("Bihar", "Patna", 25.59, 85.14),
    "chhattisgarh": ("Chhattisgarh", "Raipur", 21.25, 81.63),
    "goa": ("Goa", "Panaji", 15.49, 73.83),
    "gujarat": ("Gujarat", "Ahmedabad", 23.02, 72.57),
    "haryana": ("Haryana", "Karnal", 29.69, 76.99),
    "himachal pradesh": ("Himachal Pradesh", "Shimla", 31.10, 77.17),
    "jharkhand": ("Jharkhand", "Ranchi", 23.34, 85.31),
    "karnataka": ("Karnataka", "Bengaluru", 12.97, 77.59),
    "kerala": ("Kerala", "Thiruvananthapuram", 8.52, 76.94),
    "madhya pradesh": ("Madhya Pradesh", "Bhopal", 23.26, 77.41),
    "maharashtra": ("Maharashtra", "Pune", 18.52, 73.86),
    "manipur": ("Manipur", "Imphal", 24.82, 93.94),
    "meghalaya": ("Meghalaya", "Shillong", 25.58, 91.89),
    "mizoram": ("Mizoram", "Aizawl", 23.73, 92.72),
    "nagaland": ("Nagaland", "Kohima", 25.67, 94.11),
    "odisha": ("Odisha", "Cuttack", 20.46, 85.88),
    "punjab": ("Punjab", "Ludhiana", 30.90, 75.85),
    "rajasthan": ("Rajasthan", "Jaipur", 26.91, 75.79),
    "sikkim": ("Sikkim", "Gangtok", 27.33, 88.61),
    "tamil nadu": ("Tamil Nadu", "Thanjavur", 10.79, 79.14),
    "telangana": ("Telangana", "Hyderabad", 17.39, 78.49),
    "tripura": ("Tripura", "Agartala", 23.83, 91.28),
    "uttar pradesh": ("Uttar Pradesh", "Lucknow", 26.85, 80.95),
    "uttarakhand": ("Uttarakhand", "Dehradun", 30.32, 78.03),
    "west bengal": ("West Bengal", "Bardhaman", 23.23, 87.86),
    "delhi": ("Delhi", "New Delhi", 28.61, 77.21),
    "jammu and kashmir": ("Jammu and Kashmir", "Srinagar", 34.08, 74.80),
    "ladakh": ("Ladakh", "Leh", 34.15, 77.58),
    "chandigarh": ("Chandigarh", "Chandigarh", 30.73, 76.78),
    "puducherry": ("Puducherry", "Puducherry", 11.94, 79.81),
    "andaman and nicobar islands": ("Andaman and Nicobar Islands", "Port Blair", 11.62, 92.73),
    "lakshadweep": ("Lakshadweep", "Kavaratti", 10.57, 72.64),
    "dadra and nagar haveli and daman and diu": ("Dadra and Nagar Haveli and Daman and Diu", "Daman", 20.40, 72.83),
}
STATE_ALIASES = {
    "orissa": "odisha", "up": "uttar pradesh", "mp": "madhya pradesh", "ap": "andhra pradesh",
    "hp": "himachal pradesh", "tn": "tamil nadu", "wb": "west bengal", "uk": "uttarakhand",
    "uttaranchal": "uttarakhand", "j&k": "jammu and kashmir", "jk": "jammu and kashmir",
    "jammu & kashmir": "jammu and kashmir", "kashmir": "jammu and kashmir", "bengal": "west bengal",
    "pondicherry": "puducherry", "new delhi": "delhi", "nct of delhi": "delhi",
    "andaman": "andaman and nicobar islands", "andaman & nicobar": "andaman and nicobar islands",
    "daman": "dadra and nagar haveli and daman and diu", "chattisgarh": "chhattisgarh",
}

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


def _normalise(name: str) -> str:
    key = re.sub(r"\s+", " ", name.strip().lower().replace(".", ""))
    key = re.sub(r"\s+(state|district|ut)$", "", key)
    return STATE_ALIASES.get(key, key)


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

    key = _normalise(district)
    if key in DISTRICTS:
        lat, lon = DISTRICTS[key]
        return {"name": key.title(), "lat": lat, "lon": lon, "source": "district table"}
    if key in STATES:
        state, place, lat, lon = STATES[key]
        return {"name": f"{state} (weather for {place})", "lat": lat, "lon": lon, "source": "state table"}

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
        raise LocationError(f"Could not find '{district}'. Try a district, city or state name "
                            "(e.g. Ludhiana, Cuttack, Odisha) or use GPS.")
    hit = results[0]
    name = ", ".join(p for p in (hit.get("name"), hit.get("admin1")) if p)
    return {"name": name, "lat": hit["latitude"], "lon": hit["longitude"], "source": "geocoded"}
