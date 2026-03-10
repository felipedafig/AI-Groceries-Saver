"""
Reusable Streamlit UI components.
"""

import streamlit as st
from datetime import datetime, timezone

from config.settings import STORES
from models.schemas import ItemResult
from utils.pricing import calc_unit_price
from utils.time_utils import parse_time


def render_store_filters() -> list[str]:
    """Render store checkboxes and return the selected dealer IDs."""
    st.markdown("**Filter Stores:**")
    cols = st.columns(len(STORES))
    selected: list[str] = []
    for i, (name, did) in enumerate(STORES.items()):
        if cols[i].checkbox(name, value=True):
            selected.append(did)
    return selected


def render_api_source_filter() -> list[str]:
    """Render checkboxes for the data sources (Tjek and Salling)."""
    st.write("")  # Add vertical spacing
    st.markdown("**Data Source:**")
    cols = st.columns([1.2, 1.8, 4])
    selected: list[str] = []
    if cols[0].checkbox("📰 Tjek API", value=True):
        selected.append("Tjek")
    if cols[1].checkbox("🛒 Salling Group API", value=True):
        selected.append("Salling")
    return selected


def render_nearby_stores(stores: dict[str, dict]) -> None:
    """Display the list of nearby stores inside an expander."""
    if not stores:
        return
    with st.expander("📍 Nearby Stores", expanded=False):
        for _did, info in stores.items():
            st.caption(
                f"🏪 {info['name']} — {info['street']} ({info['dist']} km)"
            )


def render_best_deals(item_results: list[ItemResult]) -> None:
    """Render the *Best Deals* section for all items (without total)."""
    st.subheader("🏷️ Best Deals")

    for result in item_results:
        _render_single_deal(result)
        st.divider()





def render_upcoming_discounts(item_results: list[ItemResult]) -> None:
    """Render the *Upcoming Discounts* section.

    Shows future offers that are cheaper than the current best deal for
    each item.  Items already shown as best current deals are not
    duplicated here — only the future saving opportunity is highlighted.
    """
    now = datetime.now(timezone.utc)
    upcoming: list[dict] = []

    for result in item_results:
        best_future = result.best_future
        if best_future is None:
            continue

        best_current = result.best_current
        fp = best_future["pricing"]["price"]
        cp = result.current_min_price if result.current_min_price else float("inf")

        fu = calc_unit_price(best_future)
        cu = calc_unit_price(best_current) if best_current else None

        # Compare using unit prices when both offers have them;
        # fall back to shelf prices when neither (or only one) does.
        if fu and cu:
            is_better = fu[0] < cu[0]
        else:
            is_better = fp < cp

        if is_better:
            start = parse_time(best_future["run_from"])
            days = max(1, (start - now).days)

            price_str = f"{fp} kr"
            if fu:
                price_str += f"  ·  {fu[0]} {fu[1]}"

            upcoming.append(
                {
                    "query": result.query,
                    "heading": best_future["heading"],
                    "store": best_future["branding"]["name"],
                    "price_str": price_str,
                    "days": days,
                    "thumb": best_future.get("images", {}).get("thumb"),
                    "is_food_waste": best_future.get("is_food_waste", False),
                    "original_price": best_future.get("original_price"),
                    "unit_price": fu,
                    "current_unit_price": cu,
                }
            )

    if not upcoming:
        return

    st.subheader("📅 Upcoming Discounts")

    for deal in upcoming:
        col_img, col_text = st.columns([1, 5])
        with col_img:
            if deal["thumb"]:
                st.image(deal["thumb"], width=60)
        with col_text:
            source = _source_badge(deal) if deal.get("is_food_waste") else "📰 *Tjek*"
            st.markdown(f"**{deal['query'].title()}**")

            # Show how much cheaper vs current best (unit price or shelf)
            fu = deal.get("unit_price")
            cu = deal.get("current_unit_price")
            if fu and cu:
                saving = round(cu[0] - fu[0], 2)
                st.caption(
                    f"Better deal in ~{deal['days']} days  ·  "
                    f"saves {saving} {fu[1]} vs current"
                )
            else:
                st.caption(f"Better deal in ~{deal['days']} days")

            st.write(f"{deal['price_str']}  ·  {deal['store']}  {source}")
            st.caption(f"_{deal['heading']}_")
        st.divider()


def render_meat_clarification(meat_items: list[str]) -> None:
    """Render radio buttons asking the user whether to include processed products."""
    st.subheader("🥩 Fresh Meat or Processed?")
    st.write(
        "Some items on your list could match processed products "
        "(nuggets, burgers, ready meals). What do you prefer?"
    )
    for item in meat_items:
        st.radio(
            f"For **{item}**, do you want to include processed products "
            f"like nuggets?",
            ["Fresh meat only", "Include processed products"],
            key=f"meat_{item}",
        )


def render_milk_clarification(milk_items: list[str]) -> None:
    """Render radio buttons asking the user which Danish milk type they prefer."""
    from services.offer_service import MILK_TYPES

    st.subheader("🥛 Which Type of Milk?")
    st.write(
        "Danish milk comes in several standard types. "
        "Pick your preferred fat content, or choose **Any** to see all deals."
    )

    options = ["Any"] + list(MILK_TYPES.keys())

    for item in milk_items:
        st.radio(
            f"What type of **{item}** do you prefer?",
            options,
            key=f"milk_{item}",
        )


# ── private helpers ──────────────────────────────────────────────────


def _render_single_deal(result: ItemResult) -> None:
    """Render one item's best current deal."""
    item = result.query
    best = result.best_current

    if best:
        imgs = best.get("images") or {}
        image_url = imgs.get("thumb") or imgs.get("view")
        if image_url:
            st.image(image_url, width=60)

        up = calc_unit_price(best)
        price_str = f"{best['pricing']['price']} kr"
        if up:
            price_str += f"  ·  {up[0]} {up[1]}"

        # Source badge
        source_badge = _source_badge(best)

        st.write(
            f"**{item.title()}**: {price_str} "
            f"@ {best['branding']['name']}  {source_badge}"
        )
        st.caption(f"_{best['heading']}_")
    else:
        st.write(f"**{item.title()}**: No matching deals found nearby.")


def _source_badge(offer: dict) -> str:
    """Return a coloured badge string indicating the data source."""
    if offer.get("is_food_waste"):
        orig = offer.get("original_price")
        savings = ""
        if orig:
            savings = f" (was {orig} kr)"
        return f"♻️ **Salling Group · Food Waste**{savings}"
    return "📰 *Tjek*"
