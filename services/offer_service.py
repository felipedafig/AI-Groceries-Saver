from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

import requests
import streamlit as st

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
from services.ai_service import filter_offers_by_ai, batch_filter_offers_by_ai
from services.salling_service import fetch_food_waste_deals
from utils.pricing import offer_sort_key
from utils.time_utils import parse_time

_tjek_session = requests.Session()
_tjek_session.headers["X-Api-Key"] = TJEK_API_KEY


@st.cache_data(ttl=300)
def _cached_tjek_search(query: str) -> list[dict]:
    url = (
        f"{TJEK_BASE_URL}/offers/search"
        f"?query={query}&r_lat={USER_LAT}&r_lng={USER_LNG}"
        f"&r_radius={RADIUS_M}&limit=30"
    )
    resp = _tjek_session.get(url, timeout=10).json()
    return resp if isinstance(resp, list) else []


MEAT_TERMS: set[str] = {
    "chicken", "kylling",
    "beef", "oksekød", "okse",
    "pork", "svinekød", "svine",
    "meat", "kød",
    "minced meat", "hakket kød", "hakket",
    "steak", "bøf",
}


MILK_TERMS: set[str] = {"milk", "mælk"}

MILK_TYPES: dict[str, str] = {
    "Sødmælk (Whole, 3.5%)": "sødmælk",
    "Letmælk (Semi-skimmed, 1.5%)": "letmælk",
    "Minimælk (Low-fat, 0.5%)": "minimælk",
    "Skummetmælk (Skimmed, 0.1%)": "skummetmælk",
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

NON_BREAD_KEYWORDS: list[str] = [
    "brødblanding", "bland selv",
    "bageblanding", "bagemix",
    "gær", "yeast",
]


def prefetch_food_waste(
    dealer_ids: set[str], api_source: list[str] | None = None
) -> list[dict]:
    """Pre-fetch all food waste deals for the selected stores."""
    if api_source is None:
        api_source = ["Tjek", "Salling"]
    if "Salling" not in api_source:
        return []
    food_waste: list[dict] = []
    if "9ba51" in dealer_ids:
        food_waste.extend(fetch_food_waste_deals(NETTO_STORE_ID))
    if "93f13" in dealer_ids:
        food_waste.extend(fetch_food_waste_deals(BILKA_STORE_ID))
    return food_waste


def search_offers(query: str, dealer_ids: set[str], *, api_source: list[str] | None = None, _prefetched_food_waste: list[dict] | None = None) -> list[dict]:
    """Search for offers matching query near the user."""
    if api_source is None:
        api_source = ["Tjek", "Salling"]

    tjek_offers: list[dict] = []

    if "Tjek" in api_source:
        all_offers = _cached_tjek_search(query)
        tjek_offers = [o for o in all_offers if o.get("dealer_id") in dealer_ids]

    if _prefetched_food_waste is not None:
        food_waste_offers = _prefetched_food_waste
    else:
        food_waste_offers = []
        if "Salling" in api_source:
            if "9ba51" in dealer_ids:
                food_waste_offers.extend(fetch_food_waste_deals(NETTO_STORE_ID))
            if "93f13" in dealer_ids:
                food_waste_offers.extend(fetch_food_waste_deals(BILKA_STORE_ID))

    # Convert food waste deals to Tjek-like format
    converted_food_waste = []
    for fw in food_waste_offers:
        if query.lower() not in fw["heading"].lower():
            continue

        converted_food_waste.append({
            "id": f"fw-{fw['heading']}-{fw['price']}",
            "heading": fw["heading"],
            "pricing": {"price": fw["price"], "currency": fw["currency"]},
            "branding": {"name": fw["store"]},
            "images": {"thumb": fw["image"], "view": fw["image"]} if fw.get("image") else {},
            "run_from": datetime.now(timezone.utc).isoformat(),
            "run_till": fw["expires"] or (datetime.now(timezone.utc).replace(hour=23, minute=59)).isoformat(),
            "dealer_id": fw["dealer_id"],
            "is_food_waste": True,
            "original_price": fw["original_price"],
            "stock_unit": fw.get("stock_unit"),
        })

    return tjek_offers + converted_food_waste


def filter_relevant(query: str, offers: list[dict]) -> list[dict]:
    """Keep only offers that genuinely match the query."""
    if not offers:
        return []

    q = query.lower().strip()
    q_words = [w for w in q.split() if len(w) > 2]

    candidates = [
        o
        for o in offers
        if q in o["heading"].lower()
        or any(w in o["heading"].lower() for w in q_words)
    ]

    if not candidates:
        candidates = offers

    headings = [o["heading"] for o in candidates[:25]]
    valid_names = set(filter_offers_by_ai(query, headings))
    validated = [o for o in candidates if o["heading"] in valid_names]

    return validated


def batch_filter_relevant(
    items_with_offers: dict[str, list[dict]],
) -> dict[str, list[dict]]:
    """Filter offers for multiple items using a single AI call."""
    if not items_with_offers:
        return {}

    candidates_map: dict[str, list[dict]] = {}
    for query, offers in items_with_offers.items():
        if not offers:
            candidates_map[query] = []
            continue

        q = query.lower().strip()
        q_words = [w for w in q.split() if len(w) > 2]

        candidates = [
            o for o in offers
            if q in o["heading"].lower()
            or any(w in o["heading"].lower() for w in q_words)
        ]
        if not candidates:
            candidates = offers

        candidates_map[query] = candidates[:25]

    items_with_headings: dict[str, list[str]] = {
        query: [o["heading"] for o in cands]
        for query, cands in candidates_map.items()
        if cands
    }

    if items_with_headings:
        valid_map = batch_filter_offers_by_ai(items_with_headings)
    else:
        valid_map = {}

    result: dict[str, list[dict]] = {}
    for query, cands in candidates_map.items():
        valid_names = set(valid_map.get(query, []))
        if valid_names:
            result[query] = [o for o in cands if o["heading"] in valid_names]
        else:
            # If AI returned nothing (or item had no candidates), keep
            # whatever the keyword filter found so we don't lose results.
            result[query] = cands

    return result


def is_meat_item(query: str) -> bool:
    return query.lower().strip() in MEAT_TERMS


def is_milk_item(query: str) -> bool:
    return query.lower().strip() in MILK_TERMS


def is_bread_item(query: str) -> bool:
    return query.lower().strip() in {"bread", "brød"}


def filter_milk_offers(
    offers: list[dict], preferred_type: str | None
) -> list[dict]:
    if not preferred_type:
        return offers
    filtered = [
        o for o in offers if preferred_type in o["heading"].lower()
    ]
    return filtered if filtered else offers


def filter_processed_products(
    offers: list[dict], allow_processed: bool
) -> list[dict]:
    if allow_processed:
        return offers
    return [
        o for o in offers
        if not any(kw in o["heading"].lower() for kw in PROCESSED_KEYWORDS)
    ]


def filter_non_bread(offers: list[dict]) -> list[dict]:
    return [
        o for o in offers
        if not any(kw in o["heading"].lower() for kw in NON_BREAD_KEYWORDS)
    ]


def filter_bread_type(offers: list[dict], preferred_type: str) -> list[dict]:
    if preferred_type == "Both":
        return offers

    # Frozen bread keywords in Danish
    frozen_keywords = ["frost", "frossen", "frosset", "bake-off", "bake off"]
    if preferred_type == "Frozen bread":
        filtered = [
            o for o in offers
            if any(kw in o["heading"].lower() for kw in frozen_keywords)
        ]
        return filtered if filtered else offers

    if preferred_type == "Normal (fresh) bread":
        filtered = [
            o for o in offers
            if not any(kw in o["heading"].lower() for kw in frozen_keywords)
        ]
        return filtered if filtered else offers

    return offers


def separate_current_and_future_offers(
    offers: list[dict], now: datetime | None = None
) -> tuple[list[dict], list[dict]]:
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
    return min(offers, key=offer_sort_key) if offers else None


def find_best_future_offer(offers: list[dict]) -> Optional[dict]:
    return min(offers, key=offer_sort_key) if offers else None


def find_best_offers(
    items: list[str],
    nearby_ids: set[str],
    meat_prefs: dict[str, bool] | None = None,
    milk_prefs: dict[str, str] | None = None,
) -> tuple[list[ItemResult], float]:
    if meat_prefs is None:
        meat_prefs = {}
    if milk_prefs is None:
        milk_prefs = {}

    now = datetime.now(timezone.utc)
    food_waste = prefetch_food_waste(nearby_ids)

    def _process(item: str) -> ItemResult:
        offers = search_offers(item, nearby_ids, _prefetched_food_waste=food_waste)
        relevant = filter_relevant(item, offers)

        if is_meat_item(item):
            allow = meat_prefs.get(item, True)
            relevant = filter_processed_products(relevant, allow)

        if is_milk_item(item):
            preferred = milk_prefs.get(item)
            relevant = filter_milk_offers(relevant, preferred)

        if is_bread_item(item):
            relevant = filter_non_bread(relevant)

        current, future = separate_current_and_future_offers(relevant, now)
        best_current = find_best_current_offer(current)
        best_future = find_best_future_offer(future)

        return ItemResult(
            query=item,
            best_current=best_current,
            best_future=best_future,
            current_min_price=(
                best_current["pricing"]["price"] if best_current else None
            ),
        )

    with ThreadPoolExecutor(max_workers=min(len(items), 8)) as executor:
        future_map = {executor.submit(_process, item): item for item in items}
        results_map: dict[str, ItemResult] = {}
        for future in as_completed(future_map):
            results_map[future_map[future]] = future.result()

    item_results = [results_map[item] for item in items]
    total_price = sum(
        r.current_min_price for r in item_results if r.current_min_price is not None
    )

    return item_results, total_price
