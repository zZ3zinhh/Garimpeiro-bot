# Decides whether a deal is interesting for a person.
import re
import unicodedata

from stores import is_trusted_store

# Friendly categories a person can follow, and their name on each site.
#   promobit / pelando: the category (or community) names on each site
#   blocked: words that block CATEGORY alerts of this category (tag alerts have
#            their own blocked words per tag)
# Pelando only has a few broad communities, so a category only gets one when it
# fits well (a "phones" alert must not fire for a hot graphics-card deal).
CATEGORIES = {
    "computers":     {"label": "Informática", "promobit": ["informatica"],
                      "pelando": ["tech-lover"], "blocked": ["notebook", "pc gamer", "computador"]},
    "games":         {"label": "Games", "promobit": ["games"],
                      "pelando": ["mundo-gamer"], "blocked": ["notebook", "pc gamer"]},
    "phones":        {"label": "Celulares e tablets", "promobit": ["smartphones-tablets-e-telefones"]},
    "electronics":   {"label": "Eletrônicos, áudio e vídeo", "promobit": ["eletronicos-audio-e-video"]},
    "cameras":       {"label": "Câmeras e drones", "promobit": ["cameras-filmadoras-e-drones"]},
    "appliances":    {"label": "Eletrodomésticos", "promobit": ["eletrodomesticos", "eletroportateis"]},
    "home":          {"label": "Casa e decoração",
                      "promobit": ["moveis-e-decoracao", "cama-mesa-e-banho",
                                   "utensilios-domesticos", "casa-e-construcao"],
                      "pelando": ["para-meu-lar"]},
    "tools":         {"label": "Ferramentas e jardim", "promobit": ["ferramentas-e-jardim"]},
    "fashion_men":   {"label": "Moda masculina", "promobit": ["moda-e-calcados-masculinos"],
                      "pelando": ["para-eles"]},
    "fashion_women": {"label": "Moda feminina", "promobit": ["moda-e-calcados-femininos"],
                      "pelando": ["para-elas"]},
    "watches":       {"label": "Relógios e joias", "promobit": ["relogios-e-joias"]},
    "bags":          {"label": "Mochilas e malas", "promobit": ["mochilas-e-malas"]},
    "kids":          {"label": "Bebês e crianças", "promobit": ["bebes-e-criancas"],
                      "pelando": ["para-minha-familia"]},
    "toys":          {"label": "Brinquedos e hobbies", "promobit": ["brinquedos-e-hobbies"]},
    "beauty":        {"label": "Perfumes e beleza", "promobit": ["perfumes-e-beleza"]},
    "health":        {"label": "Saúde e higiene", "promobit": ["saude-e-higiene"]},
    "fitness":       {"label": "Suplementos e fitness", "promobit": ["suplementos-e-fitness"]},
    "sports":        {"label": "Esporte e lazer", "promobit": ["esporte-e-lazer"],
                      "pelando": ["esporte-e-vida"]},
    "drinks":        {"label": "Bebidas", "promobit": ["bebidas"]},
    "market":        {"label": "Supermercado", "promobit": ["supermercado-e-delivery"]},
    "books":         {"label": "Livros e eBooks", "promobit": ["livros-ebooks-e-ereaders"]},
    "media":         {"label": "Filmes, música e séries", "promobit": ["filmes-musica-e-seriados"],
                      "pelando": ["cultura"]},
    "auto":          {"label": "Automóveis", "promobit": ["pecas-e-acessorios-para-automoveis"]},
    "travel":        {"label": "Viagens", "promobit": ["viagem"]},
    "office":        {"label": "Papelaria e escritório", "promobit": ["papelaria-e-material-de-escritorio"]},
    "pets":          {"label": "Pets", "promobit": ["petshop"]},
}


def normalize(text):
    """'Placa de Vídeo RTX 5060 Ti' -> 'placa de video rtx 5060 ti'"""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))  # remove accents
    return text.lower()


def words(text):
    """Split text into words: 'rtx 5060-ti' -> ['rtx', '5060', 'ti']"""
    return re.findall(r"[a-z0-9]+", normalize(text))


def matches_tag(title, tag_text):
    """True if ALL words of the tag appear in the title, in any order.
    Also works when written together or apart: 'rtx 5060 ti' finds 'RTX5060Ti',
    and '16gb' finds '16 GB'."""
    title_words = words(title)
    tag_words = words(tag_text)
    if not tag_words:
        return False
    joined_title = "".join(title_words)
    for word in tag_words:
        if word in title_words:
            continue
        # A word with digits ('16gb', '5060') may be split in the title ('16 GB').
        if len(word) >= 3 and any(c.isdigit() for c in word) and word in joined_title:
            continue
        break
    else:
        return True
    return "".join(tag_words) in joined_title


def has_blocked_word(title, blocked_words):
    return any(matches_tag(title, b) for b in blocked_words or [])


def tag_matches(title, tag):
    """The product, every extra keyword, and (if given) at least one brand."""
    if not matches_tag(title, tag["text"]):
        return False
    if not all(matches_tag(title, k) for k in tag.get("keywords") or []):
        return False
    brands = tag.get("brands") or []
    if brands and not any(matches_tag(title, b) for b in brands):
        return False
    return True


def check_tag(deal, tag, enrich=None):
    """Returns None (not interesting), "normal" or "absurd".
    'enrich' (optional) fetches extra info for a deal, like Promobit's price meter."""
    if not tag_matches(deal["title"], tag):
        return None
    if has_blocked_word(deal["title"], tag.get("blocked_words")):
        return None

    price = deal["price"]
    max_price = tag.get("max_price")
    if max_price and price and price > max_price:
        return None

    if tag.get("absurd_alert"):
        # 1) Price far below the market price the person typed (optional).
        market = tag.get("market_price")
        limit = tag.get("limit_pct") or 50
        if market and price and price <= market * limit / 100:
            return "absurd"
        # 2) Promobit's own price meter says "the price is incredible".
        if enrich:
            enrich(deal)
        if deal.get("meter_zone") == 1:
            return "absurd"
    return "normal"


def check_category(deal, followed):
    """'followed' is a category the person follows, e.g.
    {"category": "computers", "min_discount_pct": 50, "min_temperature": 500}
    Returns True if the deal is in that category and good enough."""
    info = CATEGORIES.get(followed["category"], {})
    site_names = info.get(deal["site"], [])
    if not any(c in site_names for c in deal["categories"]):
        return False
    if has_blocked_word(deal["title"], info.get("blocked")):
        return False

    min_discount = followed.get("min_discount_pct")
    if min_discount and deal["discount_pct"] and deal["discount_pct"] >= min_discount:
        return True

    min_temp = followed.get("min_temperature")
    if min_temp and deal["temperature"] and deal["temperature"] >= min_temp:
        return True
    return False


def _evaluate(deal, person, enrich):
    best = None
    for tag in person.get("tags", []):
        result = check_tag(deal, tag, enrich)
        if result == "absurd":
            return ("absurd", tag["text"])  # absurd is the best reason, stop here
        if result == "normal" and best is None:
            best = ("normal", tag["text"])
    if best:
        return best
    for followed in person.get("categories", []):
        if check_category(deal, followed):
            return ("category", followed["category"])
    return None


def evaluate(deal, person, enrich=None):
    """Checks all of the person's tags and categories.
    Returns (reason, detail) or None. Reasons: "absurd", "normal", "category".
    If the person only wants trusted stores, deals from other stores are dropped."""
    result = _evaluate(deal, person, enrich)
    if result and person.get("only_trusted_stores"):
        if enrich:
            enrich(deal)
        if not is_trusted_store(deal):
            return None
    return result
