# Shared helpers for every deal source (Pelando, Promobit).
import requests

# Pretend to be a normal browser, otherwise some sites refuse the request.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def download_page(url):
    """Download a web page and return its HTML as text."""
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()  # raises an error on 403, 404, 500...
    response.encoding = "utf-8"
    return response.text


def new_deal(**fields):
    """Every source returns deals in this same format (a dictionary)."""
    deal = {
        "id": None,            # e.g. "pelando:abc123" (unique, so we never alert twice)
        "site": None,          # "pelando" or "promobit"
        "title": "",
        "price": None,         # current price (number) or None
        "old_price": None,     # the "was R$ ..." price (usually only Promobit has it)
        "discount_pct": None,  # e.g. 35.0 means 35% off
        "temperature": None,   # community votes (Pelando only)
        "categories": [],      # e.g. ["informatica"] or ["tech-lover"]
        "store": "",
        "link": "",
        # Filled in later, only when needed (Promobit offer page):
        "meter_zone": None,      # Promobit price meter: 1 = "price is incredible"
        "store_verified": None,  # Promobit says the store is verified
    }
    deal.update(fields)
    return deal
