"""
Salling Group service — fetches food waste deals from the Salling Group API.
"""

import requests
import streamlit as st
from typing import List, Dict, Optional
from config.settings import SALLING_API_KEY, SALLING_BASE_URL

@st.cache_data(ttl=600)  # Cache for 10 minutes
def fetch_food_waste_deals(store_id: str) -> List[Dict]:
    """Fetch food waste deals from Salling Group API for a specific store."""
    url = f"{SALLING_BASE_URL}/food-waste/{store_id}"
    headers = {"Authorization": f"Bearer {SALLING_API_KEY}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Salling Group API returns a list of clearances
        # Structure: [{"clearances": [{"offer": {...}, "product": {...}}], "store": {...}}]
        # But for a specific storeId, it's usually the object directly or a list with one item
        
        results = []
        
        # Handle different response shapes (list vs dict)
        clearance_data = data if isinstance(data, list) else [data]
        
        for entry in clearance_data:
            store_name = entry.get("store", {}).get("brand", "Unknown Store").capitalize()
            for clearance in entry.get("clearances", []):
                offer = clearance.get("offer", {})
                product = clearance.get("product", {})
                
                # Structure the deal to be compatible with ItemResult (partially)
                # or at least consistent for merging
                deal = {
                    "heading": product.get("description") or product.get("name") or "Unknown Product",
                    "price": offer.get("newPrice"),
                    "original_price": offer.get("originalPrice"),
                    "currency": offer.get("currency", "DKK"),
                    "store": store_name,
                    "image": product.get("image"),
                    "stock_unit": offer.get("stockUnit"),  # 'each' or 'kg'
                    "expires": offer.get("endTime"),
                    "is_food_waste": True,
                    "dealer_id": "salling_food_waste" # Internal marker
                }
                results.append(deal)
        
        return results
    except Exception as e:
        st.error(f"Error fetching food waste deals: {e}")
        return []
