# Reads deals from Pelando.
# The site keeps the deals inside the "props" attribute of an <astro-island> element.
import json
from bs4 import BeautifulSoup
from .common import download_page, new_deal

SITE = "https://www.pelando.com.br"


def _unwrap(value):
    """Pelando wraps every value like [type, value]. This removes the wrapping.
    type 0 = plain value / object, type 1 = list."""
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int):
        kind, inner = value
        if kind == 0 and isinstance(inner, dict):
            return {k: _unwrap(v) for k, v in inner.items()}
        if kind == 1:
            return [_unwrap(v) for v in inner]
        return inner
    if isinstance(value, dict):
        return {k: _unwrap(v) for k, v in value.items()}
    return value


def fetch(community=None):
    """Fetch recent deals. If 'community' is given (e.g. "tech-lover"),
    fetch only that community's deals."""
    url = f"{SITE}/c/{community}" if community else f"{SITE}/recentes"
    soup = BeautifulSoup(download_page(url), "html.parser")

    deals = []
    for island in soup.find_all("astro-island"):
        if "FeedContent" not in island.get("component-url", ""):
            continue  # not the deal list
        data = {k: _unwrap(v) for k, v in json.loads(island["props"]).items()}

        for d in data.get("initialDeals", []):
            if d.get("status") != "active":
                continue  # expired deal
            deals.append(new_deal(
                id="pelando:" + d["id"],
                site="pelando",
                title=d.get("title", ""),
                price=d.get("price"),
                discount_pct=d.get("discountPercentage"),
                temperature=d.get("temperature"),
                categories=[community] if community else [],
                store=(d.get("store") or {}).get("name", ""),
                link=f"{SITE}/d/{d['slug']}",
            ))
    return deals
