"""
offline_explain.py
==================
Built-in explanation used when no AI service is available (no API key,
service busy, quota exhausted or no internet). It fills fixed English or
Hindi sentences with the numbers from the report, so the farmer always gets
a readable summary. Other languages fall back to English.
"""

import re

HI_CROPS = {
    "rice": "धान", "wheat": "गेहूं", "maize": "मक्का", "chickpea": "चना", "kidneybeans": "राजमा",
    "pigeonpeas": "अरहर", "mothbeans": "मोठ", "mungbean": "मूंग", "blackgram": "उड़द", "lentil": "मसूर",
    "cotton": "कपास", "jute": "जूट", "watermelon": "तरबूज", "muskmelon": "खरबूजा", "banana": "केला",
    "papaya": "पपीता", "mango": "आम", "grapes": "अंगूर", "pomegranate": "अनार", "apple": "सेब",
    "orange": "संतरा", "coconut": "नारियल", "coffee": "कॉफी",
}
HI_SEASONS = {"Kharif": "खरीफ", "Rabi": "रबी", "Zaid": "जायद"}
HI_STATUS = {"Low": "कम", "Medium": "मध्यम", "Sufficient": "पर्याप्त", "High": "ज़्यादा"}
HI_NUTRIENTS = {"N": "नाइट्रोजन", "P": "फॉस्फोरस", "K": "पोटाश"}
HI_UNIT_NOTES = {"(paddy)": "(धान)", "(fibre)": "(रेशा)", "(seed cotton)": "(बिनौले सहित कपास)",
                 "(clean coffee)": "(साफ कॉफी)", "nuts/acre": "नारियल प्रति एकड़"}
NUTRIENT_ORDER = ("N", "P", "K")

# English limiting-factor messages from yield_model.py -> Hindi
HI_FACTORS = [
    (r"Rain covers only (\d+) of (\d+)\+ mm needed - plan irrigation",
     r"बारिश केवल \1 मिमी होगी, फसल को \2+ मिमी पानी चाहिए – सिंचाई की योजना बनाएं"),
    (r"Water shortage: (\d+) mm rain vs ([\d-]+) mm needed",
     r"पानी की कमी: बारिश \1 मिमी, ज़रूरत \2 मिमी"),
    (r"Excess rain \((\d+) mm\) - ensure drainage", r"ज़्यादा बारिश (\1 मिमी) – खेत से पानी निकलने का इंतज़ाम रखें"),
    (r"Too cold: average ([\d.]+) C vs ideal ([\d-]+) C", r"ठंड ज़्यादा: औसत \1°C, सही तापमान \2°C"),
    (r"Too hot: average ([\d.]+) C vs ideal ([\d-]+) C", r"गर्मी ज़्यादा: औसत \1°C, सही तापमान \2°C"),
    (r"Cold spells down to ([-\d.]+) C \(crop tolerates ([-\d]+) C\)", r"ठंड \1°C तक जा सकती है (फसल \2°C तक सहती है)"),
    (r"Heat spells up to ([\d.]+) C \(crop tolerates (\d+) C\)", r"गर्मी \1°C तक जा सकती है (फसल \2°C तक सहती है)"),
    (r"Low sunlight during the season", r"इस मौसम में धूप कम रहती है"),
    (r"High humidity - watch for fungal disease", r"नमी ज़्यादा – फफूंद रोग पर नज़र रखें"),
    (r"Soil N is low \((\d+)% of crop requirement\)", r"मिट्टी में नाइट्रोजन कम है (ज़रूरत का \1%)"),
    (r"Soil P is low \((\d+)% of crop requirement\)", r"मिट्टी में फॉस्फोरस कम है (ज़रूरत का \1%)"),
    (r"Soil K is low \((\d+)% of crop requirement\)", r"मिट्टी में पोटाश कम है (ज़रूरत का \1%)"),
    (r"Soil pH outside the crop's preferred range", r"मिट्टी का pH इस फसल के लिए सही दायरे से बाहर है"),
]
HI_STAGES = {
    "Basal, at sowing": "बुवाई के समय", "Basal, at transplanting": "रोपाई के समय",
    "Crown root initiation (first irrigation)": "पहली सिंचाई पर", "Tillering / jointing": "कल्ले निकलते समय",
    "Tillering": "कल्ले निकलते समय", "Panicle initiation": "बाली बनते समय", "Knee-high stage": "घुटने तक ऊंचाई पर",
    "Tasseling": "झंडे निकलते समय", "Square formation": "कली बनते समय", "Flowering": "फूल आने पर",
    "Vine running": "बेल फैलते समय", "Before flowering": "फूल आने से पहले",
    "First weeding": "पहली निराई पर", "Second weeding": "दूसरी निराई पर",
    "First half, at planting / start of season": "पहली आधी खुराक, रोपाई / मौसम की शुरुआत में",
    "Second half, 3 months later": "दूसरी आधी खुराक, 3 महीने बाद",
}


def _hi_factor(text: str) -> str:
    for pattern, repl in HI_FACTORS:
        if re.fullmatch(pattern, text):
            return re.sub(pattern, repl, text)
    return text


def _round(x: float) -> str:
    return f"{x:.0f}" if x >= 10 else f"{x:.1f}"


def _products(items, hindi):
    joiner = ", "
    return joiner.join(f"{p['product']} {p['kg_per_acre']} {'किलो' if hindi else 'kg'}" for p in items)


def offline_explanation(result: dict, crop_index: int, language: str) -> str:
    hindi = language == "hi"
    crops = result["top_crops"]
    sel = crops[crop_index]
    best = crops[0]
    season = result["season"]["name"]
    w = result["season_weather"]["mean"]
    f = sel["fertilizer"]

    def name(c):
        return HI_CROPS.get(c, c) if hindi else c.capitalize()

    def yld(c):
        y = c["yield"]["per_acre"]
        unit = y["unit"].replace("quintal/acre", "क्विंटल प्रति एकड़" if hindi else "quintal per acre")
        if hindi:
            for en, hi in HI_UNIT_NOTES.items():
                unit = unit.replace(en, hi)
        return f"{_round(y['expected'])} {unit}"

    risks = best["yield"]["limiting_factors"][:3] if sel is best else sel["yield"]["limiting_factors"][:3]
    needs_water = any("Rain covers" in r or "Water shortage" in r for c in crops for r in c["yield"]["limiting_factors"])
    soil = f["soil_status"]

    if hindi:
        lines = [
            "🗓️ आपका मौसम",
            f"यह {HI_SEASONS.get(season, season)} का मौसम है। इन महीनों में औसत तापमान लगभग {w['avg_temp']:.0f}°C "
            f"और कुल बारिश लगभग {w['total_rainfall']:.0f} मिमी रहती है।"
            + (" फसल के लिए सिंचाई की ज़रूरत होगी।" if needs_water else ""),
            "",
            "🌾 आपके लिए सबसे अच्छी फसल",
            f"{name(best['crop'])} आपके लिए सबसे अच्छी फसल है। यह लगभग {best['growing_days']} दिन में तैयार होगी "
            f"और अनुमानित पैदावार {yld(best)} है।",
            "",
            "⚖️ दूसरे विकल्प",
        ]
        others = [c for c in crops if c is not best]
        lines += [f"{name(c['crop'])}: लगभग {yld(c)}, {c['growing_days']} दिन में तैयार।" for c in others] \
            or ["इन हालात में केवल यही फसल उपयुक्त है।"]
        nut = ", ".join(f"{HI_NUTRIENTS[k]} {HI_STATUS[soil['nutrients'][k]['status']]}" for k in NUTRIENT_ORDER)
        lines += [
            "",
            "🌱 आपकी मिट्टी",
            f"{name(sel['crop'])} के लिए: {nut}। मिट्टी का pH {soil['ph']['value']} है"
            + (", जो इस फसल के लिए ठीक है।" if soil["ph"]["suits_crop"] else ", जो इस फसल के लिए सही दायरे से बाहर है।"),
            "",
            f"🧪 {name(sel['crop'])} के लिए खाद योजना (प्रति एकड़)",
            "कुल खरीदें: " + ", ".join(f"{p['product']} {p['kg_per_acre']} किलो (लगभग {p['bags_per_acre']} बोरी)"
                                       for p in f["total_products"]) + "।",
        ]
        lines += [f"{s['date']} ({HI_STAGES.get(s['stage'], s['stage'])}): {_products(s['products'], True)} डालें।"
                  for s in f["schedule"]]
        lines += ["", "⚠️ ध्यान रखें"]
        lines += [f"• {_hi_factor(r)}" for r in risks] or ["• कोई बड़ा जोखिम नहीं मिला।"]
        lines += ["• बुवाई से पहले अच्छी सड़ी गोबर की खाद (लगभग 4 टन प्रति एकड़) डालें।"]
    else:
        lines = [
            "🗓️ Your season",
            f"This is the {season} season. In these months the average temperature is about {w['avg_temp']:.0f}°C "
            f"and total rainfall is about {w['total_rainfall']:.0f} mm."
            + (" The crop will need irrigation." if needs_water else ""),
            "",
            "🌾 Best crop for you",
            f"{name(best['crop'])} is the best crop for you. It takes about {best['growing_days']} days and the expected "
            f"harvest is {yld(best)}.",
            "",
            "⚖️ Other choices",
        ]
        others = [c for c in crops if c is not best]
        lines += [f"{name(c['crop'])}: about {yld(c)}, ready in {c['growing_days']} days." for c in others] \
            or ["Only this crop suits these conditions."]
        nut = ", ".join(f"{soil['nutrients'][k]['name']} {soil['nutrients'][k]['status'].lower()}" for k in NUTRIENT_ORDER)
        lines += [
            "",
            "🌱 Your soil",
            f"For {name(sel['crop']).lower()}: {nut}. Soil pH is {soil['ph']['value']}"
            + (", which suits this crop." if soil["ph"]["suits_crop"] else ", outside this crop's preferred range."),
            "",
            f"🧪 Fertilizer plan for {name(sel['crop']).lower()} (per acre)",
            "Buy in total: " + ", ".join(f"{p['product']} {p['kg_per_acre']} kg (about {p['bags_per_acre']} bags)"
                                        for p in f["total_products"]) + ".",
        ]
        lines += [f"{s['date']} ({s['stage']}): apply {_products(s['products'], False)}." for s in f["schedule"]]
        lines += ["", "⚠️ Be careful about"]
        lines += [f"• {r}" for r in risks] or ["• No major risks found."]
        lines += ["• Add well-rotted farmyard manure (about 4 t per acre) before sowing."]
    return "\n".join(lines)
