"""
crop_calendar.py
================
Agronomic reference data for the 23 crops (22 Kaggle + wheat) in the recommendation dataset,
plus helpers that turn a planting date into an Indian cropping season.

Values are typical Indian figures (ICAR / FAO EcoCrop ranges, national
average yields) and are meant as reasonable defaults for a student project,
not field-calibrated constants.
"""

from datetime import date

KHARIF = "Kharif"
RABI = "Rabi"
ZAID = "Zaid"
PERENNIAL = "Perennial"

# Planting month -> season (India)
#   Kharif: monsoon sowing, June - September
#   Rabi:   winter sowing, October - January
#   Zaid:   summer sowing, February - May
_MONTH_TO_SEASON = {
    6: KHARIF, 7: KHARIF, 8: KHARIF, 9: KHARIF,
    10: RABI, 11: RABI, 12: RABI, 1: RABI,
    2: ZAID, 3: ZAID, 4: ZAID, 5: ZAID,
}

SEASON_INFO = {
    KHARIF: "Monsoon season - sown Jun-Sep, harvested Sep-Dec",
    RABI: "Winter season - sown Oct-Jan, harvested Mar-May",
    ZAID: "Summer season - sown Feb-May, harvested May-Jul",
}

# seasons:        seasons in which the crop is normally sown
# growing_days:   sowing -> harvest (perennials: one annual crop cycle)
# base_yield:     typical Indian yield under good management
# yield_unit:     unit of base_yield
# temp_opt:       optimal mean temperature range over the crop period (deg C)
# temp_abs:       absolute survivable mean temperature range (deg C)
# water_mm:       seasonal water requirement range (mm over the crop period)
CROPS = {
    "rice": dict(seasons=[KHARIF, ZAID], growing_days=120, base_yield=4.0, yield_unit="t/ha (paddy)",
                 temp_opt=(22, 32), temp_abs=(15, 38), water_mm=(900, 1500)),
    "wheat": dict(seasons=[RABI], growing_days=140, base_yield=4.0, yield_unit="t/ha",
                  temp_opt=(12, 22), temp_abs=(3, 30), water_mm=(350, 500)),
    "maize": dict(seasons=[KHARIF, RABI, ZAID], growing_days=100, base_yield=3.3, yield_unit="t/ha",
                  temp_opt=(18, 32), temp_abs=(10, 40), water_mm=(450, 800)),
    "chickpea": dict(seasons=[RABI], growing_days=110, base_yield=1.2, yield_unit="t/ha",
                     temp_opt=(15, 25), temp_abs=(7, 32), water_mm=(250, 450)),
    "kidneybeans": dict(seasons=[KHARIF, RABI], growing_days=100, base_yield=1.2, yield_unit="t/ha",
                        temp_opt=(16, 26), temp_abs=(10, 32), water_mm=(300, 500)),
    "pigeonpeas": dict(seasons=[KHARIF], growing_days=170, base_yield=0.9, yield_unit="t/ha",
                       temp_opt=(20, 32), temp_abs=(14, 38), water_mm=(600, 1000)),
    "mothbeans": dict(seasons=[KHARIF], growing_days=75, base_yield=0.5, yield_unit="t/ha",
                      temp_opt=(25, 35), temp_abs=(18, 42), water_mm=(200, 400)),
    "mungbean": dict(seasons=[KHARIF, ZAID], growing_days=70, base_yield=0.7, yield_unit="t/ha",
                     temp_opt=(25, 35), temp_abs=(18, 40), water_mm=(250, 400)),
    "blackgram": dict(seasons=[KHARIF, ZAID], growing_days=85, base_yield=0.7, yield_unit="t/ha",
                      temp_opt=(25, 35), temp_abs=(18, 40), water_mm=(300, 500)),
    "lentil": dict(seasons=[RABI], growing_days=115, base_yield=1.1, yield_unit="t/ha",
                   temp_opt=(15, 25), temp_abs=(6, 30), water_mm=(200, 350)),
    "cotton": dict(seasons=[KHARIF], growing_days=170, base_yield=1.5, yield_unit="t/ha (seed cotton)",
                   temp_opt=(21, 32), temp_abs=(15, 40), water_mm=(700, 1300)),
    "jute": dict(seasons=[ZAID, KHARIF], growing_days=120, base_yield=2.6, yield_unit="t/ha (fibre)",
                 temp_opt=(24, 35), temp_abs=(18, 40), water_mm=(500, 1000)),
    "watermelon": dict(seasons=[ZAID], growing_days=90, base_yield=25.0, yield_unit="t/ha",
                       temp_opt=(22, 32), temp_abs=(15, 40), water_mm=(400, 600)),
    "muskmelon": dict(seasons=[ZAID], growing_days=90, base_yield=18.0, yield_unit="t/ha",
                      temp_opt=(22, 32), temp_abs=(15, 40), water_mm=(400, 600)),
    "banana": dict(seasons=[PERENNIAL], growing_days=330, base_yield=35.0, yield_unit="t/ha",
                   temp_opt=(22, 32), temp_abs=(12, 38), water_mm=(1200, 2200)),
    "papaya": dict(seasons=[PERENNIAL], growing_days=300, base_yield=40.0, yield_unit="t/ha",
                   temp_opt=(22, 32), temp_abs=(12, 38), water_mm=(1000, 2000)),
    "mango": dict(seasons=[PERENNIAL], growing_days=365, base_yield=8.0, yield_unit="t/ha",
                  temp_opt=(22, 32), temp_abs=(8, 42), water_mm=(750, 2000)),
    "grapes": dict(seasons=[PERENNIAL], growing_days=365, base_yield=20.0, yield_unit="t/ha",
                   temp_opt=(15, 30), temp_abs=(-10, 40), water_mm=(500, 1200)),
    "pomegranate": dict(seasons=[PERENNIAL], growing_days=365, base_yield=12.0, yield_unit="t/ha",
                        temp_opt=(18, 32), temp_abs=(5, 42), water_mm=(500, 1000)),
    "apple": dict(seasons=[PERENNIAL], growing_days=365, base_yield=8.0, yield_unit="t/ha",
                  temp_opt=(7, 22), temp_abs=(-15, 30), water_mm=(1000, 1500)),
    "orange": dict(seasons=[PERENNIAL], growing_days=365, base_yield=10.0, yield_unit="t/ha",
                   temp_opt=(15, 30), temp_abs=(5, 38), water_mm=(900, 1500)),
    "coconut": dict(seasons=[PERENNIAL], growing_days=365, base_yield=10000, yield_unit="nuts/ha",
                    temp_opt=(24, 32), temp_abs=(18, 38), water_mm=(1300, 2500)),
    "coffee": dict(seasons=[PERENNIAL], growing_days=365, base_yield=0.8, yield_unit="t/ha (clean coffee)",
                   temp_opt=(18, 28), temp_abs=(12, 32), water_mm=(1500, 2500)),
}

# Window used to fetch weather *before* a crop is chosen (feeds the
# recommendation model). ~4 months covers most field-crop seasons.
DEFAULT_WINDOW_DAYS = 120


def season_for_date(planting_date: date) -> str:
    return _MONTH_TO_SEASON[planting_date.month]


def crop_fits_season(crop: str, season: str) -> bool:
    seasons = CROPS[crop]["seasons"]
    return PERENNIAL in seasons or season in seasons


def growing_days(crop: str) -> int:
    return CROPS[crop]["growing_days"]
