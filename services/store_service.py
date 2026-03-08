"""
Store service — retrieves and filters nearby stores from the Tjek API.
"""

import requests

from config.settings import TJEK_API_KEY, TJEK_BASE_URL, USER_LAT, USER_LNG, RADIUS_M
from utils.geo import haversine_km


def get_nearby_stores(dealer_ids: list[str]) -> dict[str, dict]:
    """Fetch stores from the API and return those within the configured radius.

    Args:
        dealer_ids: Dealer IDs to filter on.

    Returns:
        A dict keyed by dealer_id with values ``{name, street, dist}``.
        Only the closest location per dealer is kept.
    """
    url = (
        f"{TJEK_BASE_URL}/stores"
        f"?r_lat={USER_LAT}&r_lng={USER_LNG}&r_radius={RADIUS_M}"
        f"&dealer_ids={','.join(dealer_ids)}&limit=50"
    )
    resp = requests.get(url, headers={"X-Api-Key": TJEK_API_KEY}).json()

    nearby: dict[str, dict] = {}
    radius_km = RADIUS_M / 1000

    for store in resp:
        dist = haversine_km(USER_LAT, USER_LNG, store["latitude"], store["longitude"])
        if dist > radius_km:
            continue

        did = store["dealer_id"]
        if did not in nearby or dist < nearby[did]["dist"]:
            nearby[did] = {
                "name": store["branding"]["name"],
                "street": store["street"],
                "dist": round(dist, 2),
            }

    return nearby
