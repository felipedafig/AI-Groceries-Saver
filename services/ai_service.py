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

    Returns:
        A list of matching heading strings.
    """
    prompt = (
        f"From these product names, which ones are actually '{query}' "
        f"(the grocery item)?\nProducts: {headings}\n"
        "Return ONLY a JSON list of matching product names. "
        "If none match, return []."
    )
    try:
        resp = AI_MODEL.generate_content(prompt)
        raw = _strip_markdown_fences(resp.text.strip())
        return json.loads(raw)
    except Exception:
        return []


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
