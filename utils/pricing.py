"""
Pricing utility functions.
"""

from typing import Optional


def calc_unit_price(offer: dict) -> Optional[tuple[float, str]]:
    """Calculate the unit price for an offer.

    Returns:
        A tuple of (unit_price, label) e.g. ``(50.0, 'kr/kg')``,
        or ``None`` if the required quantity data is missing.
    """
    try:
        q = offer["quantity"]
        si_symbol = q["unit"]["si"]["symbol"]   # 'kg', 'l', or 'pcs'
        factor = q["unit"]["si"]["factor"]       # e.g. 0.001 for grams
        size_from = q["size"]["from"]
        pieces = q["pieces"]["from"] or 1
        price = offer["pricing"]["price"]

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
