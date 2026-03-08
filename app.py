import streamlit as st
import requests
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
TJEK_API_KEY = os.getenv("TJEK_API_KEY")

st.set_page_config(page_title="Horsens Grocery Saver", layout="centered")

st.title("🛒 Horsens Grocery Saver")
st.info("Searching Lidl, Løvbjerg, Netto, & Føtex in 8700")

# User Input
user_list = st.text_area("What's on the list?", placeholder="e.g. 2 mælk, vin til 50 kr, smør...")

if st.button("🚀 Find Cheapest Deals"):
    if not user_list:
        st.error("Write something first!")
    else:
        model = genai.GenerativeModel('gemini-2.5-flash')

        ai_resp = model.generate_content(f"Extract items from this text: '{user_list}'. Return ONLY a Python list of strings.")
        
        try:
            items = eval(ai_resp.text.strip().strip("`").replace("python", ""))
            total_price = 0.0

            for item in items:
                url = f"https://api.etilbudsavis.dk/v2/offers/search?query={item}&r_lat=55.8607&r_lng=9.8503&r_radius=5000"
                data = requests.get(url, headers={"X-Api-Key": TJEK_API_KEY}).json()

                if data:
                    best = min(data, key=lambda x: x['pricing']['price'])
                    price = best['pricing']['price']
                    total_price += price
                    
                    st.image(best['images']['thumb'], width=60)
                    st.write(f"**{item.title()}**: {price} kr @ {best['branding']['name']}")
                    st.divider()

            st.metric("Total Cost", f"{total_price:.2f} DKK")
        except:
            st.error("Could not read list. Try again.")