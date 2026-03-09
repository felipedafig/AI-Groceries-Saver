"""
Application configuration and environment variables.
"""

import os

import google.generativeai as genai
from dotenv import load_dotenv

# ─── Load environment variables ───
load_dotenv()

# ─── API Keys ───
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
TJEK_API_KEY: str = os.getenv("TJEK_API_KEY", "")
SALLING_API_KEY: str = os.getenv("SALLING_API_KEY", "SG_APIM_S4K1H4NJ9YY6FSXM366FT29GTWZA0R5R12DKYS30HVX5TTFMFV7G")

# ─── Salling Group Food Waste Config ───
SALLING_BASE_URL: str = "https://api.sallinggroup.com/v1"
NETTO_STORE_ID: str = "07631afc-e5b9-4561-a21f-1b72174aff50"  # Netto at Levysgade 2, Horsens
BILKA_STORE_ID: str = "a53014d5-cd36-471c-a192-69aa1d4c8c89"  # Bilka at Høegh Guldbergsgade 10, Horsens

# ─── Gemini AI Configuration ───
genai.configure(api_key=GEMINI_API_KEY)
AI_MODEL = genai.GenerativeModel("gemini-2.5-flash")

# ─── User Location (Horsens, Denmark) ───
USER_LAT: float = 55.8607
USER_LNG: float = 9.8503
RADIUS_M: int = 2500  # 2.5 km

# ─── Supported Store Dealer IDs ───
STORES: dict[str, str] = {
    "Lidl": "71c90",
    "Løvbjerg": "65caN",
    "Bilka": "93f13",
    "Netto": "9ba51",
    "365discount": "DWZE1w",
}

# ─── API Base URL ───
TJEK_BASE_URL: str = "https://api.etilbudsavis.dk/v2"
