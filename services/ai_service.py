"""
AI service — handles all interactions with the Gemini generative model.
"""

import json
import re
from typing import Any

from config.settings import AI_MODEL


def extract_grocery_items(user_text: str) -> dict[str, Any]:
    """Use Gemini to extract grocery items from a free-text Danish shopping list.

    Returns:
        A dict with keys ``"items"`` (list[str]) and ``"ambiguous"`` (dict).
    """
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

    resp = AI_MODEL.generate_content(prompt)
    raw = _strip_markdown_fences(resp.text.strip())

    try:
        parsed = json.loads(raw)
        return {
            "items": parsed.get("items", []),
            "ambiguous": parsed.get("ambiguous", {}),
        }
    except (json.JSONDecodeError, ValueError):
        return _fallback_parse(raw)


def filter_offers_by_ai(query: str, headings: list[str]) -> list[str]:
    """Ask the AI which product headings actually match the grocery *query*.

    Uses a detailed prompt to avoid false positives where a keyword
    appears inside an unrelated product name (e.g. "mælk" inside
    "MÆLKESNACK MUNCHMALLOW").

    Returns:
        A list of matching heading strings.
    """
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
        resp = AI_MODEL.generate_content(prompt)
        raw = _strip_markdown_fences(resp.text.strip())
        result = json.loads(raw)
        # Ensure we only return headings that were actually in the input
        valid = set(headings)
        return [h for h in result if h in valid]
    except Exception:
        return headings  # fail-open: return all if AI is unavailable


# ── private helpers ──────────────────────────────────────────────────


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code-block fences from AI responses."""
    text = re.sub(r"^```\w*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _fallback_parse(raw: str) -> dict[str, Any]:
    """Best-effort parse when the AI response is not well-formed JSON."""
    try:
        if raw.startswith("["):
            items = json.loads(raw)
        else:
            items = [s.strip().strip("\"'") for s in raw.strip("[]").split(",")]
        return {"items": items, "ambiguous": {}}
    except Exception:
        return {"items": [], "ambiguous": {}}
