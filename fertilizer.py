"""
fertilizer.py
=============
Soil status + fertilizer guidance for a chosen crop.

  1. Soil status: each nutrient is rated against what the crop needs
     (the crop's median soil profile in the recommendation dataset), and
     pH is classified.
  2. Dose: the crop's recommended dose of fertilizer (RDF, kg/ha of
     N - P2O5 - K2O, typical ICAR values) is adjusted by soil status, the
     usual soil-test-based rule: low +25%, sufficient -25%, high -50%.
  3. Products: the dose is converted to DAP, urea and MOP, in kg and
     50 kg bags per hectare and per acre.
  4. Schedule: basal dose at sowing, urea top dressings at crop stages,
     with calendar dates from the planting date.
  5. Amendments: lime / gypsum for pH, zinc for cereals on alkaline soil,
     farmyard manure for every crop.

Doses for fruit crops are per hectare per year for a mature orchard.
"""

from datetime import date, timedelta

# Nutrient content of common fertilizers (fraction by weight)
UREA_N = 0.46
DAP_N, DAP_P = 0.18, 0.46
MOP_K = 0.60
BAG_KG = 50
HA_PER_ACRE = 0.4047

# Recommended dose, kg/ha: (N, P2O5, K2O)
RDF = {
    "rice": (120, 60, 40),
    "wheat": (120, 60, 40),
    "maize": (150, 75, 40),
    "chickpea": (20, 50, 20),
    "kidneybeans": (90, 60, 30),
    "pigeonpeas": (25, 50, 25),
    "mothbeans": (20, 40, 0),
    "mungbean": (20, 40, 20),
    "blackgram": (20, 40, 20),
    "lentil": (20, 40, 20),
    "cotton": (120, 60, 60),
    "jute": (60, 30, 30),
    "watermelon": (100, 60, 60),
    "muskmelon": (100, 60, 60),
    "banana": (600, 180, 900),
    "papaya": (500, 500, 1000),
    "mango": (100, 50, 100),
    "grapes": (300, 200, 400),
    "pomegranate": (250, 100, 100),
    "apple": (175, 90, 175),
    "orange": (170, 55, 85),
    "coconut": (90, 55, 210),
    "coffee": (120, 90, 120),
}

PULSES = {"chickpea", "kidneybeans", "pigeonpeas", "mothbeans", "mungbean", "blackgram", "lentil"}
CEREALS = {"rice", "wheat", "maize"}

# Nitrogen split: (stage name, days after sowing, share of N).
# The first entry (day 0) is the basal dose that also carries all P and K.
N_SCHEDULE = {
    "rice": [("Basal, at transplanting", 0, 0.5), ("Tillering", 25, 0.25), ("Panicle initiation", 55, 0.25)],
    "wheat": [("Basal, at sowing", 0, 0.5), ("Crown root initiation (first irrigation)", 21, 0.25),
              ("Tillering / jointing", 45, 0.25)],
    "maize": [("Basal, at sowing", 0, 1 / 3), ("Knee-high stage", 30, 1 / 3), ("Tasseling", 55, 1 / 3)],
    "cotton": [("Basal, at sowing", 0, 1 / 3), ("Square formation", 45, 1 / 3), ("Flowering", 75, 1 / 3)],
    "jute": [("Basal, at sowing", 0, 0.5), ("First weeding", 25, 0.25), ("Second weeding", 45, 0.25)],
    "watermelon": [("Basal, at sowing", 0, 0.5), ("Vine running", 30, 0.25), ("Flowering", 45, 0.25)],
    "muskmelon": [("Basal, at sowing", 0, 0.5), ("Vine running", 30, 0.25), ("Flowering", 45, 0.25)],
    "kidneybeans": [("Basal, at sowing", 0, 0.5), ("Before flowering", 30, 0.5)],
}
PULSE_SCHEDULE = [("Basal, at sowing", 0, 1.0)]
# Fruit crops: whole dose (N, P and K) split evenly over the year
PERENNIAL_SCHEDULE = [("First half, at planting / start of season", 0, 0.5), ("Second half, 3 months later", 90, 0.5)]
PERENNIALS = {"banana", "papaya", "mango", "grapes", "pomegranate", "apple", "orange", "coconut", "coffee"}

# Soil status -> dose multiplier
DOSE_ADJUST = {"Low": 1.25, "Medium": 1.0, "Sufficient": 0.75, "High": 0.5}

NUTRIENT_NAMES = {"N": "Nitrogen", "P": "Phosphorus", "K": "Potassium"}


def _nutrient_status(value: float, need: float) -> str:
    if need <= 0:
        return "Sufficient"
    ratio = value / need
    if ratio < 0.6:
        return "Low"
    if ratio < 1.0:
        return "Medium"
    if ratio < 1.5:
        return "Sufficient"
    return "High"


def _ph_status(ph: float) -> str:
    if ph < 5.5:
        return "Strongly acidic"
    if ph < 6.5:
        return "Slightly acidic"
    if ph <= 7.5:
        return "Neutral"
    if ph <= 8.5:
        return "Alkaline"
    return "Strongly alkaline"


def soil_status(soil: dict, soil_profile: dict) -> dict:
    """Rate N, P, K against the crop's needs and classify pH."""
    nutrients = {}
    for n in ("N", "P", "K"):
        need = soil_profile[n]
        nutrients[n] = {
            "name": NUTRIENT_NAMES[n],
            "value": soil[n],
            "crop_need": need,
            "percent_of_need": round(100 * soil[n] / need) if need else None,
            "status": _nutrient_status(soil[n], need),
        }
    ph_lo, ph_hi = round(soil_profile["ph_low"], 1), round(soil_profile["ph_high"], 1)
    return {
        "nutrients": nutrients,
        "ph": {
            "value": soil["ph"],
            "status": _ph_status(soil["ph"]),
            "crop_range": [ph_lo, ph_hi],
            "suits_crop": ph_lo <= soil["ph"] <= ph_hi,
        },
    }


def _products(n: float, p2o5: float, k2o: float) -> dict:
    """kg/ha of DAP, urea and MOP that supply the given nutrients."""
    dap = p2o5 / DAP_P
    urea = max(0.0, n - dap * DAP_N) / UREA_N
    mop = k2o / MOP_K
    return {"DAP": dap, "Urea": urea, "MOP": mop}


def _product_rows(kg_per_ha: dict) -> list:
    rows = []
    for name, kg in kg_per_ha.items():
        if kg < 0.5:
            continue
        rows.append({
            "product": name,
            "kg_per_ha": round(kg),
            "kg_per_acre": round(kg * HA_PER_ACRE),
            "bags_per_acre": round(kg * HA_PER_ACRE / BAG_KG, 1),
        })
    return rows


def _schedule(crop: str, dose: dict, planting_date: date) -> list:
    n, p, k = dose["N"], dose["P2O5"], dose["K2O"]

    if crop in PERENNIALS:
        steps = []
        for stage, day, share in PERENNIAL_SCHEDULE:
            steps.append({
                "stage": stage,
                "day": day,
                "date": f"{planting_date + timedelta(days=day):%d %b %Y}",
                "products": _product_rows(_products(n * share, p * share, k * share)),
            })
        return steps

    plan = PULSE_SCHEDULE if crop in PULSES else N_SCHEDULE.get(crop, PULSE_SCHEDULE)
    steps = []
    for i, (stage, day, share) in enumerate(plan):
        if i == 0:
            # Basal: all P and K (via DAP + MOP) plus this share of N
            products = _products(n * share, p, k)
        else:
            products = {"Urea": n * share / UREA_N}
        steps.append({
            "stage": stage,
            "day": day,
            "date": f"{planting_date + timedelta(days=day):%d %b %Y}",
            "products": _product_rows(products),
        })
    return steps


def _amendments(crop: str, soil: dict, status: dict) -> list:
    notes = []
    ph = soil["ph"]
    if ph < 5.5:
        notes.append("Apply agricultural lime 2-4 t/ha (0.8-1.6 t/acre) 2-3 weeks before sowing to raise pH.")
    elif ph > 8.5:
        notes.append("Apply gypsum 2-5 t/ha (0.8-2 t/acre) before sowing to reclaim alkaline soil.")
    elif not status["ph"]["suits_crop"]:
        lo, hi = status["ph"]["crop_range"]
        notes.append(f"pH {ph} is outside this crop's preferred {lo}-{hi}; organic matter helps buffer it.")

    if crop in CEREALS and ph > 7.5:
        notes.append("Zinc deficiency is common on alkaline soil: apply zinc sulphate 25 kg/ha (10 kg/acre) at sowing.")
    if crop in PULSES:
        notes.append("Treat seed with Rhizobium and PSB culture - pulses fix their own nitrogen, so only a starter N dose is given.")
        notes.append("Apply sulphur 20 kg/ha (e.g. via gypsum or SSP) for better grain filling.")
    if crop in PERENNIALS:
        notes.append("Doses are for a mature orchard per year; use 1/4 to 1/2 for young plants. Apply in a ring around each tree.")

    notes.append("Add well-rotted farmyard manure 10 t/ha (4 t/acre) before sowing to improve soil health.")
    return notes


def fertilizer_plan(crop: str, soil: dict, soil_profile: dict, planting_date: date) -> dict:
    status = soil_status(soil, soil_profile)
    base_n, base_p, base_k = RDF[crop]

    adjust = {n: DOSE_ADJUST[status["nutrients"][n]["status"]] for n in ("N", "P", "K")}
    dose = {
        "N": round(base_n * adjust["N"]),
        "P2O5": round(base_p * adjust["P"]),
        "K2O": round(base_k * adjust["K"]),
    }

    return {
        "soil_status": status,
        "recommended_dose": {"N": base_n, "P2O5": base_p, "K2O": base_k},
        "adjusted_dose": dose,
        "dose_per_acre": {k: round(v * HA_PER_ACRE) for k, v in dose.items()},
        "total_products": _product_rows(_products(dose["N"], dose["P2O5"], dose["K2O"])),
        "schedule": _schedule(crop, dose, planting_date),
        "amendments": _amendments(crop, soil, status),
    }
