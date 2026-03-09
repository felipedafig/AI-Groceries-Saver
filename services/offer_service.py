"""
Offer service — searches, filters, and selects the best grocery offers.
"""

from datetime import datetime, timezone
from typing import Optional

import requests

from config.settings import (
    TJEK_API_KEY,
    TJEK_BASE_URL,
    USER_LAT,
    USER_LNG,
    RADIUS_M,
    NETTO_STORE_ID,
    BILKA_STORE_ID,
)
from models.schemas import ItemResult
from services.ai_service import filter_offers_by_ai
from services.salling_service import fetch_food_waste_deals
from utils.pricing import offer_sort_key
from utils.time_utils import parse_time

# ─── Meat / processed-food constants ─────────────────────────────────

MEAT_TERMS: set[str] = {
    "chicken", "kylling",
    "beef", "oksekød", "okse",
    "pork", "svinekød", "svine",
    "meat", "kød",
    "minced meat", "hakket kød", "hakket",
    "steak", "bøf",
}

PROCESSED_KEYWORDS: list[str] = [
    "nuggets", "breaded", "paneret",
    "frozen", "frost", "frossen",
    "ready", "færdig",
    "meal", "måltid", "ret",
    "box", "kasse",
    "burger",
    "snack",
    "fried", "stegt",
    "pølse", "sausage",
    "toast",
]


def search_offers(query: str, dealer_ids: set[str]) -> list[dict]:
    """Search the Tjek API for offers matching *query* near the user.

    Only offers from the specified dealer IDs are returned.
    """
    url = (
        f"{TJEK_BASE_URL}/offers/search"
        f"?query={query}&r_lat={USER_LAT}&r_lng={USER_LNG}"
        f"&r_radius={RADIUS_M}&limit=30"
    )
    resp = requests.get(url, headers={"X-Api-Key": TJEK_API_KEY}).json()
    if not isinstance(resp, list):
        tjek_offers = []
    else:
        tjek_offers = [o for o in resp if o.get("dealer_id") in dealer_ids]

    # ─── Integrated Salling Group Food Waste deals ───
    food_waste_offers = []
    
    # Only fetch food waste if Netto or Bilka are in the filter
    # Netto dealer ID in Tjek: 9ba51
    # Bilka dealer ID in Tjek: 93f13
    if "9ba51" in dealer_ids:
        food_waste_offers.extend(fetch_food_waste_deals(NETTO_STORE_ID))
    if "93f13" in dealer_ids:
        food_waste_offers.extend(fetch_food_waste_deals(BILKA_STORE_ID))

    # Convert food waste deals to Tjek-like structure for the filtering pipeline
    converted_food_waste = []
    for fw in food_waste_offers:
        # Check if the query matches the food waste deal heading
        if query.lower() not in fw["heading"].lower():
            continue
            
        converted_food_waste.append({
            "id": f"fw-{fw['heading']}-{fw['price']}",
            "heading": fw["heading"],
            "pricing": {"price": fw["price"], "currency": fw["currency"]},
            "branding": {"name": fw["store"]},
            "images": {"view": fw["image"]} if fw["image"] else None,
            "run_from": datetime.now(timezone.utc).isoformat(),
            "run_till": fw["expires"] or (datetime.now(timezone.utc).replace(hour=23, minute=59)).isoformat(),
            "dealer_id": fw["dealer_id"],
            "is_food_waste": True, # Custom flag
            "original_price": fw["original_price"]
        })

    return tjek_offers + converted_food_waste


def filter_relevant(query: str, offers: list[dict]) -> list[dict]:
    """Keep only offers that genuinely match *query*.

    Uses keyword matching first; falls back to an AI call for tricky cases.
    """
    if not offers:
        return []

    q = query.lower().strip()
    q_words = [w for w in q.split() if len(w) > 2]

    matched = [
        o
        for o in offers
        if q in o["heading"].lower()
        or any(w in o["heading"].lower() for w in q_words)
    ]
    if matched:
        return matched

    # AI fallback
    headings = [o["heading"] for o in offers[:10]]
    valid_names = filter_offers_by_ai(query, headings)
    return [o for o in offers if o["heading"] in valid_names]


def is_meat_item(query: str) -> bool:
    """Return True if *query* looks like a generic meat search term."""
    return query.lower().strip() in MEAT_TERMS


def filter_processed_products(
    offers: list[dict], allow_processed: bool
) -> list[dict]:
    """Remove processed / boxed meat products when *allow_processed* is False."""
    if allow_processed:
        return offers
    return [
        o for o in offers
        if not any(kw in o["heading"].lower() for kw in PROCESSED_KEYWORDS)
    ]


def separate_current_and_future_offers(
    offers: list[dict], now: datetime | None = None
) -> tuple[list[dict], list[dict]]:
    """Partition offers into currently-active and future lists."""
    if now is None:
        now = datetime.now(timezone.utc)
    current: list[dict] = []
    future: list[dict] = []
    for o in offers:
        if parse_time(o["run_from"]) <= now:
            current.append(o)
        else:
            future.append(o)
    return current, future


def find_best_current_offer(offers: list[dict]) -> Optional[dict]:
    """Return the offer with the lowest effective price, or None."""
    return min(offers, key=offer_sort_key) if offers else None


def find_best_future_offer(offers: list[dict]) -> Optional[dict]:
    """Return the future offer with the lowest effective price, or None."""
    return min(offers, key=offer_sort_key) if offers else None


def find_best_offers(
    items: list[str],
    nearby_ids: set[str],
    meat_prefs: dict[str, bool] | None = None,
) -> tuple[list[ItemResult], float]:
    """For each item find the best current and best future offer.

    Args:
        items: Grocery item names to search for.
        nearby_ids: Set of dealer IDs to restrict results.
        meat_prefs: Mapping of item→allow_processed for meat items.

    Returns:
        A tuple of (item_results, total_estimated_price).
    """
    if meat_prefs is None:
        meat_prefs = {}

    now = datetime.now(timezone.utc)
    total_price = 0.0
    item_results: list[ItemResult] = []

    for item in items:
        offers = search_offers(item, nearby_ids)
        relevant = filter_relevant(item, offers)

        # Apply processed-food filter for meat items
        if is_meat_item(item):
            allow = meat_prefs.get(item, True)
            relevant = filter_processed_products(relevant, allow)

        current, future = separate_current_and_future_offers(relevant, now)

        best_current = find_best_current_offer(current)
        best_future = find_best_future_offer(future)

        if best_current:
            total_price += best_current["pricing"]["price"]

        item_results.append(
            ItemResult(
                query=item,
                best_current=best_current,
                best_future=best_future,
                current_min_price=(
                    best_current["pricing"]["price"] if best_current else None
                ),
            )
        )

    return item_results, total_price
