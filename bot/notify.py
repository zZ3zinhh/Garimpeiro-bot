# Sends the alerts: ntfy (always) and WhatsApp via CallMeBot (if the person wants).
# The notification text is in Portuguese because friends and family read it.
from urllib.parse import quote_plus

import requests

from matcher import CATEGORIES


def format_brl(value):
    """2574.5 -> 'R$ 2.574,50'"""
    if value is None:
        return ""
    text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + text


def build_message(deal, reason, detail):
    """Returns (title, body) for the notification."""
    if reason == "absurd":
        title = f"🔥 PROMOÇÃO ABSURDA: {detail}"
    elif reason == "category":
        title = f"💸 Promoção em {CATEGORIES.get(detail, {}).get('label', detail)}"
    else:
        title = f"🔔 {detail}"

    lines = [deal["title"]]
    price = format_brl(deal["price"])
    if price:
        if deal["old_price"]:
            price += f" (era {format_brl(deal['old_price'])})"
        lines.append(price)

    extras = []
    if deal["discount_pct"]:
        extras.append(f"-{deal['discount_pct']:.0f}%")
    if deal["temperature"] is not None:
        extras.append(f"{deal['temperature']}°")
    if deal["store"]:
        extras.append(deal["store"])
    extras.append(deal["site"].capitalize())
    lines.append(" · ".join(extras))

    # Extra signals, only when we know them (we open the Promobit page for some deals).
    if deal.get("meter_zone") == 1:
        lines.append("📉 O Promobit marca este preço como incrível")
    if deal.get("store_verified"):
        lines.append("✅ Loja verificada pelo Promobit")
    return title, "\n".join(lines)


def reputation_link(deal):
    """A Google search for the store's Reclame Aqui page (the real API is not free)."""
    if not deal.get("store"):
        return None
    return "https://www.google.com/search?q=" + quote_plus(f"reclame aqui {deal['store']}")


def send_ntfy(topic, title, body, link, urgent=False, store_link=None):
    """Send to the ntfy app. We use JSON because it handles accents and emojis."""
    message = {
        "topic": topic,
        "title": title,
        "message": body,
        "click": link,                     # tapping the notification opens the deal
        "priority": 5 if urgent else 3,    # 5 = max, 3 = default
        "tags": ["rotating_light"] if urgent else ["shopping_cart"],
    }
    if store_link:  # a button under the notification
        message["actions"] = [{"action": "view", "label": "Reputação da loja", "url": store_link}]
    requests.post("https://ntfy.sh/", json=message, timeout=30).raise_for_status()


def send_whatsapp(phone, apikey, title, body, link):
    """Send a private WhatsApp message via CallMeBot (free, only to your own number)."""
    text = f"*{title}*\n{body}\n{link}"
    requests.get("https://api.callmebot.com/whatsapp.php", params={
        "phone": phone, "text": text, "apikey": apikey,
    }, timeout=30).raise_for_status()


def alert(person, deal, reason, detail):
    title, body = build_message(deal, reason, detail)
    send_ntfy(person["ntfy_topic"], title, body, deal["link"],
              urgent=(reason == "absurd"), store_link=reputation_link(deal))

    whatsapp = person.get("whatsapp") or {}
    if whatsapp.get("enabled") and whatsapp.get("phone") and whatsapp.get("apikey"):
        try:
            send_whatsapp(whatsapp["phone"], whatsapp["apikey"], title, body, deal["link"])
        except Exception as error:  # if WhatsApp fails, ntfy already went through
            print("   ! WhatsApp failed:", error)
