"""
Horsens Grocery Saver — Streamlit entry point.

Reads a shopping list, uses Gemini AI to extract items, queries the
Tjek (etilbudsavis) API for grocery discounts near Horsens, and
presents the cheapest deals to the user.
"""

import streamlit as st

from ui.components import render_store_filters
from ui.pages import handle_clarify, handle_extract, handle_meat_clarify, handle_milk_clarify, handle_results, handle_search

# ─── Page configuration ───
st.set_page_config(page_title="Horsens Grocery Saver", layout="centered")
st.title("🛒 Horsens Grocery Saver")

# ─── Store filters ───
selected_dealers = render_store_filters()

# ─── User input ───
user_list = st.text_area(
    "What's on the list?",
    placeholder="e.g. 2 mælk, vin til 50 kr, smør...",
)

# ─── Session state initialisation ───
for key, default in [
    ("phase", "input"),
    ("clear_items", []),
    ("ambiguous", {}),
    ("results", None),
    ("meat_prefs", {}),
    ("milk_prefs", {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─── Button: Extract items ───
if st.button("🚀 Find Cheapest Deals"):
    handle_extract(user_list, selected_dealers)

# ─── Phase: Clarification ───
if st.session_state.phase == "clarify":
    handle_clarify()

# ─── Phase: Meat clarification ───
if st.session_state.phase == "meat_clarify":
    handle_meat_clarify()

# ─── Phase: Milk clarification ───
if st.session_state.phase == "milk_clarify":
    handle_milk_clarify()

# ─── Phase: Search ───
if st.session_state.phase == "search":
    handle_search(selected_dealers)

# ─── Phase: Display results ───
if st.session_state.phase == "results" and st.session_state.results:
    handle_results()