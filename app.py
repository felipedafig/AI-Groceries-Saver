import streamlit as st

from ui.components import render_store_filters, render_api_source_filter
from ui.pages import (
    handle_bread_clarify,
    handle_clarify,
    handle_extract,
    handle_meat_clarify,
    handle_milk_clarify,
    handle_results,
    handle_search,
)

st.set_page_config(page_title="Horsens Grocery Saver", layout="centered")
st.title("🛒 Horsens Grocery Saver")

import uuid
if "_rate_limit_id" not in st.session_state:
    st.session_state["_rate_limit_id"] = uuid.uuid4().hex

selected_dealers = render_store_filters()
api_source = render_api_source_filter()

user_list = st.text_area(
    "What's on the list?",
    placeholder="e.g. 2 mælk, vin til 50 kr, smør...",
)

for key, default in [
    ("phase", "input"),
    ("clear_items", []),
    ("ambiguous", {}),
    ("results", None),
    ("meat_prefs", {}),
    ("milk_prefs", {}),
    ("bread_prefs", {}),
    ("api_source", ["Tjek", "Salling"]),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if st.button("🚀 Find Cheapest Deals"):
    st.session_state.api_source = api_source
    handle_extract(user_list, selected_dealers)

if st.session_state.phase == "clarify":
    handle_clarify()

if st.session_state.phase == "bread_clarify":
    handle_bread_clarify()

if st.session_state.phase == "meat_clarify":
    handle_meat_clarify()

if st.session_state.phase == "milk_clarify":
    handle_milk_clarify()

if st.session_state.phase == "search":
    handle_search(selected_dealers, st.session_state.get("api_source", ["Tjek", "Salling"]))

if st.session_state.phase == "results" and st.session_state.results:
    handle_results()