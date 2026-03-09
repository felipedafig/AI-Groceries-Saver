"""
Streamlit page-level logic for each phase of the application.
"""

import streamlit as st

from models.schemas import ItemResult, SearchResults
from services.ai_service import extract_grocery_items
from services.offer_service import (
    find_best_offers,
    is_meat_item,
    is_milk_item,
    filter_milk_offers,
    search_offers,
    filter_relevant,
    filter_processed_products,
    separate_current_and_future_offers,
    find_best_current_offer,
    find_best_future_offer,
    MILK_TYPES,
)
from services.store_service import get_nearby_stores
from ui.components import (
    render_best_deals,
    render_meat_clarification,
    render_milk_clarification,
    render_nearby_stores,
    render_total_price,
    render_upcoming_discounts,
)


def handle_extract(user_list: str, selected_dealers: list[str]) -> None:
    """Phase: extract grocery items from the user's free-text list."""
    if not user_list:
        st.error("Write something first!")
        return
    if not selected_dealers:
        st.error("Select at least one store!")
        return

    with st.spinner("🤖 Reading your list..."):
        try:
            parsed = extract_grocery_items(user_list)
        except Exception as e:
            st.error(f"AI call failed: {e}")
            st.stop()

    st.session_state.clear_items = parsed["items"]
    st.session_state.ambiguous = parsed["ambiguous"]
    st.session_state.results = None
    st.session_state.meat_prefs = {}
    st.session_state.milk_prefs = {}

    st.session_state.phase = "clarify" if parsed["ambiguous"] else _next_phase_after_clarify()
    st.rerun()


def handle_clarify() -> None:
    """Phase: let the user disambiguate vague items."""
    st.subheader("🤔 Did you mean...")

    for term, options in st.session_state.ambiguous.items():
        st.radio(f"**{term}**:", options, key=f"clarify_{term}")

    if st.button("✅ Confirm & Search"):
        for term in st.session_state.ambiguous:
            choice = st.session_state.get(f"clarify_{term}")
            if choice:
                st.session_state.clear_items.append(choice)
        st.session_state.ambiguous = {}
        st.session_state.phase = _next_phase_after_clarify()
        st.rerun()


def handle_meat_clarify() -> None:
    """Phase: ask whether the user wants processed products for meat items."""
    meat_items = [i for i in st.session_state.clear_items if is_meat_item(i)]

    render_meat_clarification(meat_items)

    if st.button("✅ Confirm Meat Preferences"):
        prefs: dict[str, bool] = {}
        for item in meat_items:
            choice = st.session_state.get(f"meat_{item}", "Include processed products")
            prefs[item] = choice == "Include processed products"
        st.session_state.meat_prefs = prefs
        st.session_state.phase = _next_phase_after_meat()
        st.rerun()


def handle_milk_clarify() -> None:
    """Phase: ask for milk type preferences."""
    milk_items = [i for i in st.session_state.clear_items if is_milk_item(i)]

    render_milk_clarification(milk_items)

    if st.button("✅ Confirm Milk Preferences"):
        prefs: dict[str, str] = {}
        for item in milk_items:
            choice = st.session_state.get(f"milk_{item}", "Any")
            if choice != "Any":
                prefs[item] = MILK_TYPES[choice]
        st.session_state.milk_prefs = prefs
        st.session_state.phase = "search"
        st.rerun()


def handle_search(selected_dealers: list[str]) -> None:
    """Phase: query the API for offers and store results in session state."""
    items = st.session_state.clear_items
    st.session_state.phase = "results"

    if not items:
        st.warning("No items found in your list.")
        st.stop()

    with st.spinner("📍 Finding nearby stores..."):
        nearby = get_nearby_stores(selected_dealers)

    if not nearby:
        st.warning("No stores found within 2.5 km.")
        st.session_state.results = SearchResults(stores={})
    else:
        nearby_ids = set(nearby.keys())
        meat_prefs = getattr(st.session_state, "meat_prefs", {}) or {}
        milk_prefs = getattr(st.session_state, "milk_prefs", {}) or {}

        item_results, total_price = _search_items_with_spinners(
            items, nearby_ids, meat_prefs, milk_prefs
        )

        st.session_state.results = SearchResults(
            items=item_results,
            total=total_price,
            stores=nearby,
        )

    st.session_state.clear_items = []
    st.rerun()


def handle_results() -> None:
    """Phase: display search results, best deals, and upcoming discounts.

    Order: Best Deals → Upcoming Discounts → Total Estimated Price.
    """
    data: SearchResults = st.session_state.results
    if data is None:
        return

    render_nearby_stores(data.stores)

    if not data.items:
        st.warning("No stores found within 2.5 km.")
        return

    render_best_deals(data.items)
    render_upcoming_discounts(data.items)
    render_total_price(data.total)


# ── private helpers ──────────────────────────────────────────────────


def _next_phase_after_clarify() -> str:
    """Decide whether we need a meat-clarification step or can go to search."""
    meat_items = [i for i in st.session_state.clear_items if is_meat_item(i)]
    if meat_items:
        return "meat_clarify"
    return _next_phase_after_meat()


def _next_phase_after_meat() -> str:
    """Decide whether we need a milk-clarification step or can go to search."""
    milk_items = [i for i in st.session_state.clear_items if is_milk_item(i)]
    if milk_items:
        return "milk_clarify"
    return "search"


def _search_items_with_spinners(
    items: list[str],
    nearby_ids: set[str],
    meat_prefs: dict[str, bool],
    milk_prefs: dict[str, str],
) -> tuple[list[ItemResult], float]:
    """Search offers per item with Streamlit spinners for UX feedback."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    total_price = 0.0
    item_results: list[ItemResult] = []

    for item in items:
        with st.spinner(f"Searching for {item}..."):
            offers = search_offers(item, nearby_ids)
            relevant = filter_relevant(item, offers)

        # Apply processed-food filter for meat items
        if is_meat_item(item):
            allow = meat_prefs.get(item, True)
            relevant = filter_processed_products(relevant, allow)

        # Apply milk type filter (falls back to all milk if preferred type has no deals)
        if is_milk_item(item):
            preferred = milk_prefs.get(item)
            relevant = filter_milk_offers(relevant, preferred)

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
