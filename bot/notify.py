# Sends the alerts: ntfy (always) and WhatsApp via CallMeBot (if the person wants).
# The notification text is in Portuguese because friends and family read it.
import requests

# How each category name shows up in the notification
CATEGORY_LABELS = {
    "computers": "Informática",
    "games": "Games",
    "phones": "Celulares",
    "electronics": "Eletrônicos",
}


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
        title = f"💸 Promoção em {CATEGORY_LABELS.get(detail, detail)}"
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
    return title, "\n".join(lines)


def send_ntfy(topic, title, body, link, urgent=False):
    """Send to the ntfy app. We use JSON because it handles accents and emojis."""
    requests.post("https://ntfy.sh/", json={
        "topic": topic,
        "title": title,
        "message": body,
        "click": link,                     # tapping the notification opens the deal
        "priority": 5 if urgent else 3,    # 5 = max, 3 = default
        "tags": ["rotating_light"] if urgent else ["shopping_cart"],
    }, timeout=30).raise_for_status()


def send_whatsapp(phone, apikey, title, body, link):
    """Send a private WhatsApp message via CallMeBot (free, only to your own number)."""
    text = f"*{title}*\n{body}\n{link}"
    requests.get("https://api.callmebot.com/whatsapp.php", params={
        "phone": phone, "text": text, "apikey": apikey,
    }, timeout=30).raise_for_status()


def alert(person, deal, reason, detail):
    title, body = build_message(deal, reason, detail)
    send_ntfy(person["ntfy_topic"], title, body, deal["link"], urgent=(reason == "absurd"))

    whatsapp = person.get("whatsapp") or {}
    if whatsapp.get("enabled") and whatsapp.get("phone") and whatsapp.get("apikey"):
        try:
            send_whatsapp(whatsapp["phone"], whatsapp["apikey"], title, body, deal["link"])
        except Exception as error:  # if WhatsApp fails, ntfy already went through
            print("   ! WhatsApp failed:", error)
