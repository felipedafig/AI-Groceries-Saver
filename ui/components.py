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


def render_total_price(total: float) -> None:
    """Render the total estimated cost metric."""
    if total > 0:
        st.metric("Total Estimated Cost", f"{total:.2f} DKK")


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

        future_cmp = fu[0] if fu else fp
        current_cmp = cu[0] if cu else cp

        if future_cmp < current_cmp:
            start = parse_time(best_future["run_from"])
            days = max(1, (start - now).days)

            price_str = f"{fp} kr"
            if fu:
                price_str += f" · {fu[0]} {fu[1]}"

            upcoming.append(
                {
                    "query": result.query,
                    "heading": best_future["heading"],
                    "store": best_future["branding"]["name"],
                    "price_str": price_str,
                    "days": days,
                    "thumb": best_future.get("images", {}).get("thumb"),
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
            st.markdown(f"**{deal['query'].title()}**")
            st.caption(f"Better deal in ~{deal['days']} days")
            st.write(f"{deal['price_str']}  ·  {deal['store']}")
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


# ── private helpers ──────────────────────────────────────────────────


def _render_single_deal(result: ItemResult) -> None:
    """Render one item's best current deal."""
    item = result.query
    best = result.best_current

    if best:
        # Support for both Tjek thumb and Salling Group image
        image_url = best.get("images", {}).get("thumb") if best.get("images") else best.get("image")
        if image_url:
            st.image(image_url, width=60)
        
        up = calc_unit_price(best)
        price_str = f"{best['pricing']['price']} kr"
        if up:
            price_str += f"  ·  {up[0]} {up[1]}"
            
        # Food Waste Labeling
        fw_label = " ♻️ **Food Waste Deal**" if best.get("is_food_waste") else ""
        
        st.write(
            f"**{item.title()}**: {price_str} "
            f"@ {best['branding']['name']}{fw_label}"
        )
        st.caption(f"_{best['heading']}_")
    else:
        st.write(f"**{item.title()}**: No matching deals found nearby.")
