# Reads deals from Promobit.
# The site keeps everything inside <script id="__NEXT_DATA__"> as JSON.
import json
from bs4 import BeautifulSoup
from .common import download_page, new_deal

SITE = "https://www.promobit.com.br"


def fetch(category=None):
    """Fetch recent deals. If 'category' is given (e.g. "informatica"),
    fetch only that category's deals."""
    url = f"{SITE}/promocoes/{category}/" if category else f"{SITE}/promocoes/recentes/"
    soup = BeautifulSoup(download_page(url), "html.parser")
    page = json.loads(soup.find("script", id="__NEXT_DATA__").string)["props"]["pageProps"]

    # Lookup table to turn a category number into its name (3 -> "informatica")
    category_names = {}
    for c in page.get("__app-ctx-optional-props", {}).get("categories", []):
        category_names[c["categoryId"]] = c["categoryUrl"]

    items = (page.get("serverOffers") or {}).get("offers", [])
    items += page.get("serverFeaturedOffers") or []

    deals = []
    for d in items:
        price = d.get("offerPrice")
        if price is not None and price <= 0.01:
            price = None  # coupons show up with price 0.01
        old = d.get("offerOldPrice")
        if not old or not price or old <= price:
            old = None  # the site uses 0.01 when there is no old price

        discount = d.get("offerDiscontPercentage") or None
        if discount is None and old:
            discount = round((1 - price / old) * 100, 1)

        categories = []
        if d.get("categoryId") in category_names:
            categories.append(category_names[d["categoryId"]])
        if category and category not in categories:
            categories.append(category)

        deals.append(new_deal(
            id=f"promobit:{d['offerId']}",
            site="promobit",
            title=d.get("offerTitle", ""),
            price=price,
            old_price=old,
            discount_pct=discount,
            categories=categories,
            store=d.get("storeName", ""),
            link=f"{SITE}/oferta/{d['offerSlug']}/",
        ))
    return deals
