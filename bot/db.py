# Talks to the Supabase database through its REST API.
# Uses only the standard library (urllib), so there is nothing extra to install.
import json
import os
import urllib.request
from datetime import datetime, timezone

BOT_FOLDER = os.path.dirname(os.path.abspath(__file__))
PAGE_SIZE = 1000  # Supabase returns at most 1000 rows per request by default


def _read_env_file():
    values = {}
    with open(os.path.join(BOT_FOLDER, ".env"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


_env = _read_env_file()
_BASE_URL = _env["SUPABASE_URL"].rstrip("/") + "/rest/v1/"
_KEY = _env["SUPABASE_SECRET_KEY"]


def _request(method, path, body=None, prefer=None):
    headers = {
        "apikey": _KEY,
        "Authorization": "Bearer " + _KEY,
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(_BASE_URL + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8")
        return json.loads(text) if text else None


def load_people():
    """Everyone who gets alerts, with their tags and categories.
    The shape matches what matcher.py and notify.py expect."""
    rows = _request("GET", "people?select=*,tags(*),followed_categories(*)")
    people = []
    for row in rows:
        people.append({
            "id": row["id"],
            "name": row["name"],
            "ntfy_topic": row["ntfy_topic"],
            "whatsapp": {
                "enabled": row["whatsapp_enabled"],
                "phone": row["whatsapp_phone"],
                "apikey": row["whatsapp_apikey"],
            },
            "tags": [
                {
                    "text": t["text"],
                    "blocked_words": t["blocked_words"],
                    "max_price": t["max_price"],
                    "absurd_alert": t["absurd_alert"],
                    "market_price": t["market_price"],
                    "limit_pct": t["limit_pct"],
                }
                for t in row["tags"]
            ],
            "categories": [
                {
                    "category": c["category"],
                    "min_discount_pct": c["min_discount_pct"],
                    "min_temperature": c["min_temperature"],
                }
                for c in row["followed_categories"]
            ],
        })
    return people


def load_sent_keys():
    """All (person, deal) pairs already alerted, as 'person_id|deal_id' strings."""
    keys = set()
    offset = 0
    while True:
        rows = _request(
            "GET",
            f"sent_alerts?select=person_id,deal_id&order=person_id.asc,deal_id.asc"
            f"&limit={PAGE_SIZE}&offset={offset}",
        )
        for row in rows:
            keys.add(f"{row['person_id']}|{row['deal_id']}")
        if len(rows) < PAGE_SIZE:
            return keys
        offset += PAGE_SIZE


def save_sent(person_id, deal_id):
    """Remember one alert right after it was sent, so a crash never sends it twice."""
    _request(
        "POST",
        "sent_alerts",
        {"person_id": person_id, "deal_id": deal_id},
        prefer="resolution=ignore-duplicates",
    )


def mark_run(runner):
    """Update the heartbeat: when the bot last ran, and where."""
    _request(
        "PATCH",
        "bot_status?id=eq.1",
        {"last_run": datetime.now(timezone.utc).isoformat(), "runner": runner},
    )
