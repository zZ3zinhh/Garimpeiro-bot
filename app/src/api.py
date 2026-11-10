# Talks to Supabase (the "safe doors") and to ntfy.
# Only uses the standard library, so there is nothing heavy to pack into the APK.
import json
import ssl
import urllib.error
import urllib.request

from settings import SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL

# Android doesn't come with the list of trusted websites, so we bring our own (certifi).
try:
    import certifi

    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # on the PC the system list is fine
    _SSL_CONTEXT = None


class ApiError(Exception):
    """An error with a message that is safe to show to the user (in Portuguese).
    'kind' tells what happened: "invalid_code", "network" or "other"."""

    def __init__(self, message, kind="other"):
        super().__init__(message)
        self.kind = kind


def _send(request):
    try:
        with urllib.request.urlopen(request, timeout=20, context=_SSL_CONTEXT) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else None
    except urllib.error.HTTPError as error:  # the server answered with an error
        body = error.read().decode("utf-8", errors="replace")
        if "invalid code" in body:
            raise ApiError("Código inválido. Confira e tente de novo.", "invalid_code")
        if "too many tags" in body:
            raise ApiError("Você chegou no limite de 50 tags.")
        raise ApiError(f"Algo deu errado (erro {error.code}).")
    except (urllib.error.URLError, TimeoutError, OSError):  # no internet, timeout...
        raise ApiError("Sem conexão com a internet. Tente de novo.", "network")


def _rpc(name, payload):
    """Calls one safe door (a function in the database)."""
    request = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{name}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Authorization": "Bearer " + SUPABASE_PUBLISHABLE_KEY,
            "Content-Type": "application/json",
        },
    )
    return _send(request)


def get_profile(code):
    return _rpc("app_get_profile", {"p_code": code})


def save_tag(code, tag_id, text, keywords, brands, blocked_words,
             max_price, absurd_alert, market_price, limit_pct):
    return _rpc("app_save_tag", {
        "p_code": code, "p_id": tag_id, "p_text": text,
        "p_keywords": keywords, "p_brands": brands, "p_blocked_words": blocked_words,
        "p_max_price": max_price, "p_absurd_alert": absurd_alert,
        "p_market_price": market_price, "p_limit_pct": limit_pct,
    })


def delete_tag(code, tag_id):
    return _rpc("app_delete_tag", {"p_code": code, "p_id": tag_id})


def save_category(code, category_id, category, min_discount_pct, min_temperature):
    return _rpc("app_save_category", {
        "p_code": code, "p_id": category_id, "p_category": category,
        "p_min_discount_pct": min_discount_pct, "p_min_temperature": min_temperature,
    })


def delete_category(code, category_id):
    return _rpc("app_delete_category", {"p_code": code, "p_id": category_id})


def save_settings(code, whatsapp_enabled, whatsapp_phone, whatsapp_apikey):
    return _rpc("app_save_settings", {
        "p_code": code, "p_whatsapp_enabled": whatsapp_enabled,
        "p_whatsapp_phone": whatsapp_phone, "p_whatsapp_apikey": whatsapp_apikey,
    })


def save_preferences(code, saved_blocked_words, only_trusted_stores):
    return _rpc("app_save_preferences", {
        "p_code": code, "p_saved_blocked_words": saved_blocked_words,
        "p_only_trusted_stores": only_trusted_stores,
    })


def recent_alerts(code):
    return _rpc("app_recent_alerts", {"p_code": code, "p_limit": 30})


def send_test_notification(topic):
    """Sends a test message to the person's ntfy channel."""
    request = urllib.request.Request(
        "https://ntfy.sh/",
        data=json.dumps({
            "topic": topic,
            "title": "✅ Teste do Garimpeiro",
            "message": "Se você está vendo isto, os avisos estão funcionando!",
            "tags": ["white_check_mark"],
        }).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    _send(request)
