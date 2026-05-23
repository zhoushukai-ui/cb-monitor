"""Internationalization — language detection and translation.

Resolution order: Cookie > Accept-Language header > IP geo > English.
IP geo uses ip-api.com (free, no key needed, 45 req/min limit, cached).
"""

import json
import logging
from pathlib import Path

import httpx

from config import BACKEND_DIR

logger = logging.getLogger(__name__)

# ── Load translation maps ──────────────────────────────────────────

TRANSLATIONS: dict[str, dict[str, str]] = {}

LOCALE_DIR = BACKEND_DIR / "locales"
for f in LOCALE_DIR.glob("*.json"):
    lang = f.stem
    with open(f, encoding="utf-8") as fh:
        TRANSLATIONS[lang] = json.load(fh)

SUPPORTED_LANGS = list(TRANSLATIONS.keys())

# ── Country → language mapping ────────────────────────────────────

COUNTRY_LANG_MAP = {
    "CN": "zh",
    "SG": "zh",
    "TW": "zh",
    "HK": "zh",
}

# ── IP geo cache ──────────────────────────────────────────────────

_ip_cache: dict[str, str] = {}


async def _geoip_country_code(client_ip: str) -> str | None:
    """Return ISO 3166-1 alpha-2 country code for an IP.

    Uses ip-api.com free endpoint. Caches results to avoid rate limits.
    Returns None on failure or for private IPs.
    """
    if not client_ip or client_ip.startswith(("10.", "172.16.", "192.168.", "127.", "::1")):
        return None

    if client_ip in _ip_cache:
        return _ip_cache[client_ip]

    try:
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"http://ip-api.com/json/{client_ip}", params={"fields": "countryCode"})
            if resp.status_code == 200:
                data = resp.json()
                cc: str = data.get("countryCode", "")
                _ip_cache[client_ip] = cc
                return cc or None
    except Exception:
        logger.debug("GeoIP lookup failed for %s", client_ip)

    _ip_cache[client_ip] = ""
    return None


# ── Language resolution ───────────────────────────────────────────

async def resolve_lang(cookie_lang: str | None, accept_language: str, client_ip: str) -> str:
    """Resolve user language.

    Priority:
      1. Cookie override (explicit user choice)
      2. Accept-Language header
      3. IP geo → country → language
      4. Default: 'en'
    """
    # 1. Cookie
    if cookie_lang in SUPPORTED_LANGS:
        return cookie_lang

    # 2. Accept-Language header
    if accept_language:
        for part in accept_language.split(","):
            code = part.split(";")[0].strip().split("-")[0].lower()
            if code == "zh":
                return "zh"
            if code == "en":
                return "en"

    # 3. IP geo
    cc = await _geoip_country_code(client_ip)
    if cc and cc in COUNTRY_LANG_MAP:
        return COUNTRY_LANG_MAP[cc]

    # 4. Default
    return "en"


# ── Translation helper ────────────────────────────────────────────

def t(lang: str, key: str, default: str | None = None) -> str:
    """Translate *key* into *lang*.

    Falls back: lang → en → key itself → *default*.
    """
    if lang in TRANSLATIONS and key in TRANSLATIONS[lang]:
        return TRANSLATIONS[lang][key]
    if "en" in TRANSLATIONS and key in TRANSLATIONS["en"]:
        return TRANSLATIONS["en"][key]
    return default or key
