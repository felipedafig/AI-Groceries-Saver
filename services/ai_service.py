import json
import re
from typing import Any

import streamlit as st

from config.settings import AI_MODEL
from utils.rate_limiter import gemini_limiter, RateLimitExceeded


def extract_grocery_items(user_text: str) -> dict[str, Any]:
    """Use Gemini to extract grocery items from a Danish shopping list."""
    prompt = (
        f"Extract grocery items from this Danish shopping list: '{user_text}'\n"
        "Return a JSON object with exactly two keys:\n"
        '- "items": list of clear, specific grocery item names in Danish\n'
        '- "ambiguous": dict where each key is an ambiguous term and value '
        "is a list of 2-3 possible specific meanings in Danish\n\n"
        "Special rules:\n"
        "- If the user asks for 'bread' or 'brød', ALWAYS treat it as ambiguous "
        "and offer these specific options: ['Brød (Frisk)', 'Brød (Frost)']\n\n"
        'Example — if input is "æbler, mælk" and æbler is ambiguous:\n'
        '{{"items": ["mælk"], "ambiguous": {{"æbler": ["æbler (frugt)", "æblejuice"]}}}}\n\n'
        "If nothing is ambiguous:\n"
        '{{"items": ["mælk", "æbler"], "ambiguous": {{}}}}\n\n'
        "Return ONLY valid JSON, no markdown fences."
    )

    session_id = st.session_state.get("_rate_limit_id", "global")
    gemini_limiter.check(session_id)

    try:
        resp = AI_MODEL.generate_content(prompt)
        raw = _strip_markdown_fences(resp.text.strip())
    except Exception as e:
        # If API fails, return the item as-is in a non-ambiguous way to let app continue
        return {"items": [user_text], "ambiguous": {}}

    try:
        parsed = json.loads(raw)
        return {
            "items": parsed.get("items", []),
            "ambiguous": parsed.get("ambiguous", {}),
        }
    except (json.JSONDecodeError, ValueError):
        return _fallback_parse(raw)


def filter_offers_by_ai(query: str, headings: list[str]) -> list[str]:
    """Ask AI which product headings actually match the grocery query."""
    prompt = (
        "You are a grocery shopping assistant.  The user has a shopping "
        f"list and wants to buy: **{query}**\n\n"
        "Below is a list of supermarket offer headings.  Return ONLY the "
        "headings that a shopper would reasonably buy to fulfil the item "
        f"'{query}' on their list.\n\n"
        "Rules:\n"
        "- Match the BASE ingredient, not products that merely contain the word.\n"
        "  Example: 'mælk' (milk) → accept 'ARLA LETMÆLK 1L', reject 'MÆLKESNACK MUNCHMALLOW'.\n"
        "  Example: 'æg' (eggs) → accept 'FRITGÅENDE ÆG 10PK', reject 'ÆG & BACON SALAT'.\n"
        "  Example: 'kylling' (chicken) → accept 'KYLLINGEBRYST 500G', reject 'KYLLING WOK GODT BEGYNDT'.\n"
        "- Ready meals, snacks, candy, sauces, salads, and dressings that "
        "  happen to contain the keyword are NOT matches.\n"
        "- The product should be the raw/plain form of the ingredient unless "
        "  the query specifically asks for something processed.\n"
        "- For 'bread' (brød), match actual bread/buns/rolls, NOT bread mixes, "
        "  flour, or baking ingredients (e.g., 'brødblanding', 'mel' are NOT bread).\n\n"
        f"Headings:\n{json.dumps(headings, ensure_ascii=False)}\n\n"
        "Return ONLY a JSON list of matching heading strings.  "
        "If none match, return [].  No explanation."
    )
    try:
        session_id = st.session_state.get("_rate_limit_id", "global")
        gemini_limiter.check(session_id)

        resp = AI_MODEL.generate_content(prompt)
        raw = _strip_markdown_fences(resp.text.strip())
        result = json.loads(raw)
        valid = set(headings)
        return [h for h in result if h in valid]
    except RateLimitExceeded:
        raise
    except Exception:
        return headings


def batch_filter_offers_by_ai(
    items_with_headings: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Filter offers for multiple grocery items in a single Gemini call."""
    if not items_with_headings:
        return {}

    payload: dict[str, list[str]] = {
        item: headings for item, headings in items_with_headings.items()
    }

    prompt = (
        "You are a grocery shopping assistant.  For each grocery item below "
        "I provide a list of supermarket offer headings.\n\n"
        "For EVERY item, return ONLY the headings that a shopper would "
        "reasonably buy to fulfil that item on their list.\n\n"
        "Rules:\n"
        "- Match the BASE ingredient, not products that merely contain the word.\n"
        "  Example: 'mælk' (milk) → accept 'ARLA LETMÆLK 1L', reject 'MÆLKESNACK MUNCHMALLOW'.\n"
        "  Example: 'æg' (eggs) → accept 'FRITGÅENDE ÆG 10PK', reject 'ÆG & BACON SALAT'.\n"
        "  Example: 'kylling' (chicken) → accept 'KYLLINGEBRYST 500G', reject 'KYLLING WOK GODT BEGYNDT'.\n"
        "- Ready meals, snacks, candy, sauces, salads, and dressings that "
        "  happen to contain the keyword are NOT matches.\n"
        "- The product should be the raw/plain form of the ingredient unless "
        "  the query specifically asks for something processed.\n"
        "- For 'bread' (brød), match actual bread/buns/rolls, NOT bread mixes, "
        "  flour, or baking ingredients (e.g., 'brødblanding', 'mel' are NOT bread).\n\n"
        f"Items and their candidate headings:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        "Return ONLY a JSON object mapping each item to its list of matching "
        "heading strings.  If no headings match for an item, use an empty list.\n"
        "Example: {\"mælk\": [\"ARLA LETMÆLK 1L\"], \"æg\": [\"FRITGÅENDE ÆG 10PK\"]}\n"
        "No explanation, no markdown fences."
    )

    try:
        session_id = st.session_state.get("_rate_limit_id", "global")
        gemini_limiter.check(session_id)

        resp = AI_MODEL.generate_content(prompt)
        raw = _strip_markdown_fences(resp.text.strip())
        result = json.loads(raw)

        filtered: dict[str, list[str]] = {}
        for item, headings in items_with_headings.items():
            valid = set(headings)
            ai_picks = result.get(item, [])
            filtered[item] = [h for h in ai_picks if h in valid]
        return filtered
    except RateLimitExceeded:
        raise
    except Exception:
        return dict(items_with_headings)


def _strip_markdown_fences(text: str) -> str:
    text = re.sub(r"^```\w*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _fallback_parse(raw: str) -> dict[str, Any]:
    try:
        if raw.startswith("["):
            items = json.loads(raw)
        else:
            items = [s.strip().strip("\"'") for s in raw.strip("[]").split(",")]
        return {"items": items, "ambiguous": {}}
    except Exception:
        return {"items": [], "ambiguous": {}}
