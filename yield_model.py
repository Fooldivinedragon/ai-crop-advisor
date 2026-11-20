"""
yield_model.py
==============
Estimates crop yield from soil + growing-period weather.

There is no yield column in the recommendation dataset, so this is a
transparent agronomic model: a typical Indian yield for the crop is scaled
by stress factors (0-1) for temperature, water, sunlight, humidity, soil
nutrients and pH. The yield is computed for each historical year's weather,
giving an expected value and a min-max range.

To replace it with a learned model, train a regressor on a yield dataset
(crop, N, P, K, ph, avg_temp, total_rainfall, avg_humidity, avg_solar ->
yield) and swap it into `predict_yield`.
"""

from crop_calendar import CROPS

# Crops that tolerate (or need) very humid conditions without extra disease loss
HUMID_TOLERANT = {"rice", "jute", "coconut", "banana", "papaya", "coffee"}

HA_PER_ACRE = 0.4047
QUINTAL_PER_ACRE = 10 * HA_PER_ACRE  # quintal/acre for 1 t/ha

# Plantation crops grown on rainfall in India - irrigation is not assumed
RAINFED_PLANTATIONS = {"coffee", "coconut", "apple"}


def _range_factor(value, opt, absolute, floor=0.3):
    """1.0 inside the optimal range, falling linearly to 0.4 at the absolute
    limit and `floor` beyond it."""
    lo, hi = opt
    abs_lo, abs_hi = absolute
    if lo <= value <= hi:
        return 1.0
    if value < lo:
        if value <= abs_lo:
            return floor
        return 1.0 - 0.6 * (lo - value) / (lo - abs_lo)
    if value >= abs_hi:
        return floor
    return 1.0 - 0.6 * (value - hi) / (abs_hi - hi)


def _factors(crop: str, soil: dict, weather: dict, soil_profile: dict, irrigated: bool) -> dict:
    info = CROPS[crop]
    f = {}

    f["temperature"] = _range_factor(weather["avg_temp"], info["temp_opt"], info["temp_abs"])

    # Coldest / hottest day of the period - catches frost or heat that a
    # long-period average hides (important for perennials)
    abs_lo, abs_hi = info["temp_abs"]
    cold = max(0.3, 1.0 - 0.2 * max(0, abs_lo - weather["min_temp"]))
    heat = max(0.3, 1.0 - 0.1 * max(0, weather["max_temp"] - abs_hi))
    f["temp_extremes"] = cold * heat

    rain = weather["total_rainfall"]
    need_lo, need_hi = info["water_mm"]
    if rain < need_lo:
        rainfed = not irrigated or crop in RAINFED_PLANTATIONS
        f["water"] = 0.3 + 0.7 * rain / need_lo if rainfed else 1.0
    elif rain > need_hi * 1.5:
        f["water"] = 0.85  # waterlogging / nutrient leaching
    else:
        f["water"] = 1.0

    solar = weather["avg_solar"]
    f["sunlight"] = 1.0 if solar >= 12 else 0.93 if solar >= 9 else 0.85

    f["humidity"] = 0.92 if weather["avg_humidity"] > 85 and crop not in HUMID_TOLERANT else 1.0

    # Liebig's law of the minimum: the scarcest nutrient limits yield
    sufficiency = {
        n: min(1.0, soil[n] / soil_profile[n]) if soil_profile[n] > 0 else 1.0
        for n in ("N", "P", "K")
    }
    f["soil_nutrients"] = min(0.6 + 0.4 * s for s in sufficiency.values())

    ph_lo, ph_hi = soil_profile["ph_low"], soil_profile["ph_high"]
    ph_off = max(ph_lo - soil["ph"], soil["ph"] - ph_hi, 0)
    f["ph"] = max(0.6, 1.0 - 0.15 * ph_off)

    return {k: round(v, 3) for k, v in f.items()}, sufficiency


def _per_acre(unit: str, expected: float, low: float, high: float) -> dict:
    """Yield in the units Indian farmers use: quintals per acre
    (1 t/ha = 10 quintal / 2.471 acre), or nuts per acre for coconut."""
    if unit.startswith("t/ha"):
        factor, new_unit, digits = QUINTAL_PER_ACRE, "quintal/acre" + unit[len("t/ha"):], 1
    else:  # "nuts/ha"
        factor, new_unit, digits = HA_PER_ACRE, unit.replace("/ha", "/acre"), 0
    return {
        "unit": new_unit,
        "expected": round(expected * factor, digits),
        "low": round(low * factor, digits),
        "high": round(high * factor, digits),
    }


def _limiting_notes(crop, factors, sufficiency, weather, irrigated):
    info = CROPS[crop]
    notes = []
    if factors["temperature"] < 1:
        lo, hi = info["temp_opt"]
        side = "cold" if weather["avg_temp"] < lo else "hot"
        notes.append(f"Too {side}: average {weather['avg_temp']:.1f} C vs ideal {lo}-{hi} C")
    rain, (need_lo, need_hi) = weather["total_rainfall"], info["water_mm"]
    if rain < need_lo:
        if irrigated and crop not in RAINFED_PLANTATIONS:
            notes.append(f"Rain covers only {rain:.0f} of {need_lo}+ mm needed - plan irrigation")
        else:
            notes.append(f"Water shortage: {rain:.0f} mm rain vs {need_lo}-{need_hi} mm needed")
    elif factors["water"] < 1:
        notes.append(f"Excess rain ({rain:.0f} mm) - ensure drainage")
    lo, hi = info["temp_abs"]
    if weather["min_temp"] < lo:
        notes.append(f"Cold spells down to {weather['min_temp']:.1f} C (crop tolerates {lo} C)")
    if weather["max_temp"] > hi:
        notes.append(f"Heat spells up to {weather['max_temp']:.1f} C (crop tolerates {hi} C)")
    if factors["sunlight"] < 1:
        notes.append("Low sunlight during the season")
    if factors["humidity"] < 1:
        notes.append("High humidity - watch for fungal disease")
    for n, s in sufficiency.items():
        if s < 0.8:
            notes.append(f"Soil {n} is low ({s:.0%} of crop requirement)")
    if factors["ph"] < 1:
        notes.append("Soil pH outside the crop's preferred range")
    return notes


def predict_yield(crop: str, soil: dict, weather: dict, soil_profile: dict, irrigated: bool = True) -> dict:
    """`weather` is the output of weather.growing_period_weather()."""
    info = CROPS[crop]
    base = info["base_yield"]

    yearly = []
    for yr in weather["per_year"]:
        factors, _ = _factors(crop, soil, yr, soil_profile, irrigated)
        total = 1.0
        for v in factors.values():
            total *= v
        yearly.append({"year": yr["year"], "yield": round(base * total, 2)})

    factors, sufficiency = _factors(crop, soil, weather["mean"], soil_profile, irrigated)
    values = [y["yield"] for y in yearly]
    expected = sum(values) / len(values)

    return {
        "crop": crop,
        "unit": info["yield_unit"],
        "expected": round(expected, 2),
        "low": min(values),
        "high": max(values),
        "potential": base,
        "percent_of_potential": round(100 * expected / base),
        "per_acre": _per_acre(info["yield_unit"], expected, min(values), max(values)),
        "by_year": yearly,
        "factors": factors,
        # How well the local climate suits the crop, independent of soil
        "climate_suitability": round(factors["temperature"] * factors["temp_extremes"] * factors["water"], 3),
        "limiting_factors": _limiting_notes(crop, factors, sufficiency, weather["mean"], irrigated),
    }
