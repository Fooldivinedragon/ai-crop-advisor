"""
explain.py
==========
Turns the whole pipeline report (season, weather, all recommended crops,
soil and the fertilizer plan for the selected crop) into one short,
simple explanation for the farmer in their language, using an LLM.

Only the numbers the system already computed are sent; the model is told
to explain them, not to invent new advice.

Two providers are supported:
  - Claude (ANTHROPIC_API_KEY) - used for the final version
  - Gemini free tier (GEMINI_API_KEY, from aistudio.google.com) - for testing
Claude is used when its key is set, otherwise Gemini. Set LLM_PROVIDER to
"claude" or "gemini" to force one.
"""

import json
import logging
import os
import time

import anthropic
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from offline_explain import offline_explanation

MODEL = "claude-opus-5-5"
# gemini-3.6-flash: good Hindi in ~15 s on the free tier (3.8-flash took 40+ s)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"
GEMINI_TIMEOUT_MS = 40_000
GEMINI_BUDGET_S = 50
PROVIDER_NAMES = {"claude": "Claude", "gemini": "Gemini"}

log = logging.getLogger(__name__)

LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "pa": "Punjabi",
    "mr": "Marathi",
    "gu": "Gujarati",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
}

SYSTEM_PROMPT = """You are a friendly agricultural extension officer in India explaining a whole \
crop advisory report to a small farmer. The farmer may have little formal education, so:

- Write in the requested language, in its native script, using everyday words a village farmer \
uses. Keep common terms farmers already know (urea, DAP, MOP, bag, acre, Kharif, Rabi) as they are.
- Use short sentences. Give harvest in quintal per acre and fertilizer per acre with 50 kg bag \
counts, exactly as in the report; never use hectares or tonnes.
- Use ONLY the facts and numbers in the report. Do not add crops, products, doses, prices or \
dates that are not in it. Round numbers sensibly (e.g. "about 1.5 bags", "about 12 quintal").
- If the report shows a risk (low nutrient, water shortage, cold, heat, pH problem), say plainly \
what to do about it, using the advice in the report.

Structure the answer as plain text (no markdown symbols like # or *), with these sections, \
each starting with its emoji and a short heading in the farmer's language:
🗓️ Your season (season, what the weather is usually like in these months, whether irrigation is needed)
🌾 Best crop for you (the first crop in the list and why it suits, in 2-3 short lines)
⚖️ Other choices (compare the crops in one line each: expected harvest, days to harvest, main \
risk; if the report has only one crop, say only this crop suits these conditions)
🌱 Your soil (one overall picture for the selected crop: which nutrients are low or fine, and the pH)
🧪 Fertilizer plan for the selected crop (what to buy in total, then what to apply on which date)
⚠️ Be careful about (the 2-3 most important risks and what to do)
Keep the whole answer under 300 words."""


class ExplainError(RuntimeError):
    pass


class ExplainRequestError(ExplainError):
    """The request itself is invalid (bad language or crop selection)."""


def _crop_summary(crop: dict) -> dict:
    y, w = crop["yield"], crop["weather"]["mean"]
    return {
        "crop": crop["crop"],
        "model_confidence_percent": round(100 * crop["probability"]),
        "suits_this_season": crop["fits_season"],
        "growing_days": crop["growing_days"],
        "expected_harvest_date": crop["expected_harvest"],
        "yield_per_acre": y["per_acre"],
        "percent_of_potential_yield": y["percent_of_potential"],
        "weather_during_crop": {k: w[k] for k in ("avg_temp", "total_rainfall", "avg_humidity")},
        "risks": y["limiting_factors"],
    }


def _compact(result: dict, crop_index: int) -> dict:
    """The whole report in compact form (no per-year data), with the soil and
    fertilizer details for the crop the farmer has selected."""
    selected = result["top_crops"][crop_index]
    f = selected["fertilizer"]
    w = result["season_weather"]
    return {
        "location": result["location"]["name"],
        "season": result["season"],
        "planting_date": result["inputs"]["planting_date"],
        "irrigation_available": result["inputs"]["irrigated"],
        "typical_season_weather": {
            "period": f"{w['window_start']} - {w['window_end']}",
            "based_on_years": w["years"],
            **w["mean"],
        },
        "crops_best_first": [_crop_summary(c) for c in result["top_crops"]],
        "selected_crop": selected["crop"],
        "soil_status_for_selected_crop": f["soil_status"],
        "fertilizer_total_per_acre": [
            {"product": p["product"], "kg": p["kg_per_acre"], "bags_50kg": p["bags_per_acre"]}
            for p in f["total_products"]
        ],
        "fertilizer_schedule_per_acre": [
            {"stage": s["stage"], "date": s["date"],
             "apply": [{"product": p["product"], "kg": p["kg_per_acre"]} for p in s["products"]]}
            for s in f["schedule"]
        ],
        "other_advice": f["amendments"],
    }


def explain(result: dict, crop_index: int = 0, language: str = "en") -> dict:
    """Returns {"text", "provider": "Claude" | "Gemini" | "offline", "offline": bool}.
    Falls back to the built-in summary when no AI service can answer."""
    if language not in LANGUAGES:
        raise ExplainRequestError(f"Unsupported language '{language}'")
    if not 0 <= crop_index < len(result.get("top_crops", [])):
        raise ExplainRequestError("Invalid crop selection")

    report = json.dumps(_compact(result, crop_index), ensure_ascii=False, indent=1)
    prompt = f"Explain this whole crop advisory report to the farmer in {LANGUAGES[language]}.\n\n<report>\n{report}\n</report>"

    try:
        provider = _pick_provider()
        text = _ask_claude(prompt) if provider == "claude" else _ask_gemini(prompt)
    except ExplainError as exc:
        # No key, service busy, quota used up or no internet: give the
        # farmer the built-in summary instead of an error
        log.warning("AI explanation unavailable, using offline summary: %s", exc)
        return {"text": offline_explanation(result, crop_index, language), "provider": "offline", "offline": True}
    return {"text": text, "provider": PROVIDER_NAMES[provider], "offline": False}


def _pick_provider() -> str:
    choice = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if choice in PROVIDER_NAMES:
        return choice
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    raise ExplainError("No AI key found - set ANTHROPIC_API_KEY (Claude) or GEMINI_API_KEY (free Gemini)")


def _ask_gemini(prompt: str) -> str:
    try:
        # Reads GEMINI_API_KEY / GOOGLE_API_KEY. The timeout is sent to Google
        # as a deadline; a slow answer comes back as a 504 ServerError.
        client = genai.Client(http_options=genai_types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
    except ValueError as exc:
        raise ExplainError("Gemini API key is missing - set GEMINI_API_KEY") from exc

    # Free-tier models are often busy (503) or slow (504): fall back to the
    # fast lite model, retrying it once before giving up
    attempts = [GEMINI_MODEL, GEMINI_FALLBACK_MODEL, GEMINI_FALLBACK_MODEL]
    started = time.monotonic()
    for i, model in enumerate(attempts):
        # Stay well inside the web server's 120 s request timeout; the
        # caller then shows the offline summary instead
        if i > 0 and time.monotonic() - started > GEMINI_BUDGET_S:
            raise ExplainError("Gemini is too slow right now")
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, max_output_tokens=4000),
            )
            break
        except genai_errors.ClientError as exc:
            if exc.code == 429:
                raise ExplainError("Gemini free-tier limit reached - please try again in a minute") from exc
            if exc.code == 403:
                raise ExplainError(f"Gemini refused this key: {exc.message}") from exc
            if exc.code in (400, 401):
                raise ExplainError("Gemini API key is missing or invalid - check GEMINI_API_KEY") from exc
            raise ExplainError(f"Gemini service error ({exc.code})") from exc
        except genai_errors.ServerError as exc:
            if i == len(attempts) - 1:
                raise ExplainError("Gemini is busy right now - please try again in a minute") from exc
            time.sleep(2)
        except genai_errors.APIError as exc:
            raise ExplainError(f"Gemini service error ({exc.code})") from exc
        except OSError as exc:
            # Network failures (no internet, DNS, connection reset)
            raise ExplainError(f"Could not reach Gemini: {exc}") from exc

    if not response.text:
        raise ExplainError("The explanation could not be generated for this report")
    return response.text.strip()


def _ask_claude(prompt: str) -> str:
    try:
        client = anthropic.Anthropic()
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            # If a safety classifier declines, retry on a fallback model in the same call
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as exc:
        raise ExplainError("Anthropic API key is missing or invalid - set ANTHROPIC_API_KEY") from exc
    except anthropic.RateLimitError as exc:
        raise ExplainError("Too many requests - please try again in a minute") from exc
    except anthropic.APIStatusError as exc:
        raise ExplainError(f"Explanation service error ({exc.status_code})") from exc
    except anthropic.APIConnectionError as exc:
        raise ExplainError("Could not reach the explanation service - check the internet connection") from exc
    except TypeError as exc:
        # The SDK raises TypeError when no API key / credentials can be resolved
        if "authentication" not in str(exc):
            raise
        raise ExplainError("Anthropic API key is missing - set ANTHROPIC_API_KEY") from exc

    if response.stop_reason == "refusal":
        raise ExplainError("The explanation could not be generated for this report")

    return "".join(b.text for b in response.content if b.type == "text").strip()
