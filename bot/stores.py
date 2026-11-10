# Which stores count as "trusted" for people who turn on "only trusted stores".
#
# Why not the Reclame Aqui API? There is no free public one for individuals, so we
# use two free signals instead:
#   1) Promobit tells us if a store is verified and has a valid CNPJ.
#   2) This list of big, well-known Brazilian stores (edit it as you like).
import unicodedata

TRUSTED_STORES = [
    "Amazon", "KaBuM", "Pichau", "Terabyte", "TerabyteShop", "Magazine Luiza", "Magalu",
    "Americanas", "Casas Bahia", "Ponto", "Fast Shop", "Carrefour", "Submarino", "Shoptime",
    "Mercado Livre", "Samsung", "Apple", "LG", "Dell", "Lenovo", "Asus", "Acer", "Nike",
    "Adidas", "Centauro", "Netshoes", "Leroy Merlin", "Drogasil", "Droga Raia", "Panvel",
    "Havan", "Extra", "Girafa", "Webmotors", "Renner", "C&A", "Riachuelo", "Natura",
    "O Boticario", "Sephora", "Booking", "Decolar", "Azul", "Gol", "LATAM",
]


def _clean(name):
    name = unicodedata.normalize("NFKD", name or "")
    name = "".join(c for c in name if not unicodedata.combining(c)).lower()
    return "".join(c for c in name if c.isalnum())


_TRUSTED = {_clean(name) for name in TRUSTED_STORES}


def is_trusted_store(deal):
    """True if Promobit verified the store, or the store is on our list."""
    if deal.get("store_verified"):
        return True
    return _clean(deal.get("store")) in _TRUSTED
