"""
Pricing utility functions.
"""

import re
from typing import Optional

# Regex to extract weight/volume from product descriptions like
# "SF HØNSESALAT 250G", "Arla Minimælk 1L", "Svinekød 0,5KG", etc.
_QTY_RE = re.compile(
    r"(\d+[.,]?\d*)\s*"
    r"(kg|g|ml|cl|dl|l|liter|stk|pk)\b",
    re.IGNORECASE,
)

# Map description units → SI base unit + conversion factor
_UNIT_CONV: dict[str, tuple[str, float]] = {
    "kg":    ("kg", 1.0),
    "g":     ("kg", 0.001),
    "l":     ("l",  1.0),
    "liter": ("l",  1.0),
    "dl":    ("l",  0.1),
    "cl":    ("l",  0.01),
    "ml":    ("l",  0.001),
    "stk":   ("pcs", 1.0),
    "pk":    ("pcs", 1.0),
}


def _parse_qty_from_heading(heading: str) -> Optional[tuple[float, str]]:
    """Try to extract a (total_si, si_symbol) tuple from a product heading.

    Examples:
        "SF HØNSESALAT 250G"  → (0.25, 'kg')
        "Arla Minimælk 1L"    → (1.0,  'l')
    """
    m = _QTY_RE.search(heading)
    if not m:
        return None
    value_str = m.group(1).replace(",", ".")
    unit_str = m.group(2).lower()
    try:
        value = float(value_str)
    except ValueError:
        return None
    conv = _UNIT_CONV.get(unit_str)
    if conv is None or value <= 0:
        return None
    si_symbol, factor = conv
    return (value * factor, si_symbol)


def calc_unit_price(offer: dict) -> Optional[tuple[float, str]]:
    """Calculate the unit price for an offer.

    Returns:
        A tuple of (unit_price, label) e.g. ``(50.0, 'kr/kg')``,
        or ``None`` if the required quantity data is missing.
    """
    price = offer.get("pricing", {}).get("price")
    if price is None:
        return None

    # ── Salling Group food waste deals ──────────────────────────
    if offer.get("is_food_waste"):
        # If the stock unit is 'kg', the price IS the per-kg price
        stock_unit = offer.get("stock_unit")
        if stock_unit and stock_unit.lower() == "kg":
            return (round(price, 2), "kr/kg")

        # Otherwise try to extract quantity from the heading text
        heading = offer.get("heading", "")
        parsed = _parse_qty_from_heading(heading)
        if parsed:
            total_si, si_symbol = parsed
            unit_price = price / total_si
            label_map = {"kg": "kr/kg", "l": "kr/l", "pcs": "kr/stk"}
            return (round(unit_price, 2), label_map.get(si_symbol, f"kr/{si_symbol}"))
        return None

    # ── Tjek offers (structured quantity data) ──────────────────
    try:
        q = offer["quantity"]
        si_symbol = q["unit"]["si"]["symbol"]   # 'kg', 'l', or 'pcs'
        factor = q["unit"]["si"]["factor"]       # e.g. 0.001 for grams
        size_from = q["size"]["from"]
        pieces = q["pieces"]["from"] or 1

        total_si = size_from * factor * pieces   # total in kg / l / pcs
        if total_si <= 0:
            return None

        unit_price = price / total_si
        label_map = {"kg": "kr/kg", "l": "kr/l", "pcs": "kr/stk"}
        label = label_map.get(si_symbol, f"kr/{si_symbol}")
        return (round(unit_price, 2), label)
    except (KeyError, TypeError, ZeroDivisionError):
        return None


def offer_sort_key(offer: dict) -> float:
    """Return a comparable price value for sorting offers.

    Uses unit price when available, otherwise falls back to shelf price.
    """
    up = calc_unit_price(offer)
    return up[0] if up else offer["pricing"]["price"]
