# Decides whether a deal is interesting for a person.
import re
import unicodedata

# Friendly categories a person can follow, and their name on each site.
CATEGORIES = {
    "computers":   {"promobit": ["informatica"], "pelando": ["tech-lover"]},
    "games":       {"promobit": ["games"], "pelando": ["mundo-gamer"]},
    "phones":      {"promobit": ["smartphones-tablets-e-telefones"], "pelando": ["tech-lover"]},
    "electronics": {"promobit": ["eletronicos-audio-e-video"], "pelando": ["tech-lover"]},
}


# Words that block CATEGORY alerts for everyone (so we only get single parts,
# not whole computers or laptops). Tag alerts have their own list per tag.
CATEGORY_BLOCKED_WORDS = ["notebook", "pc gamer", "computador"]


def normalize(text):
    """'Placa de Vídeo RTX 5060 Ti' -> 'placa de video rtx 5060 ti'"""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))  # remove accents
    return text.lower()


def words(text):
    """Split text into words: 'rtx 5060-ti' -> ['rtx', '5060', 'ti']"""
    return re.findall(r"[a-z0-9]+", normalize(text))


def matches_tag(title, tag_text):
    """True if ALL words of the tag appear in the title.
    Also works when written together: 'rtx 5060 ti' finds 'RTX5060Ti'."""
    title_words = words(title)
    tag_words = words(tag_text)
    if not tag_words:
        return False
    if all(w in title_words for w in tag_words):
        return True
    return "".join(tag_words) in "".join(title_words)


def has_blocked_word(title, blocked_words):
    return any(matches_tag(title, b) for b in blocked_words or [])


def check_tag(deal, tag):
    """Returns None (not interesting), "normal" or "absurd"."""
    if not matches_tag(deal["title"], tag["text"]):
        return None
    if has_blocked_word(deal["title"], tag.get("blocked_words")):
        return None

    price = deal["price"]
    max_price = tag.get("max_price")
    if max_price and price and price > max_price:
        return None

    # Absurd deal: price <= market price x limit%
    market = tag.get("market_price")
    limit = tag.get("limit_pct", 50)
    if tag.get("absurd_alert") and market and price and price <= market * limit / 100:
        return "absurd"
    return "normal"


def check_category(deal, followed):
    """'followed' is a category the person follows, e.g.
    {"category": "computers", "min_discount_pct": 50, "min_temperature": 500}
    Returns True if the deal is in that category and good enough."""
    site_names = CATEGORIES.get(followed["category"], {}).get(deal["site"], [])
    if not any(c in site_names for c in deal["categories"]):
        return False
    if has_blocked_word(deal["title"], CATEGORY_BLOCKED_WORDS):
        return False

    min_discount = followed.get("min_discount_pct")
    if min_discount and deal["discount_pct"] and deal["discount_pct"] >= min_discount:
        return True

    min_temp = followed.get("min_temperature")
    if min_temp and deal["temperature"] and deal["temperature"] >= min_temp:
        return True
    return False


def evaluate(deal, person):
    """Checks all of the person's tags and categories.
    Returns (reason, detail) or None. Reasons: "absurd", "normal", "category"."""
    best = None
    for tag in person.get("tags", []):
        result = check_tag(deal, tag)
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
