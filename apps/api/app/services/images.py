"""Illustrative images from Openverse, fetched server-side.

The browser never sends the user's question anywhere: the model proposes a few
generic keywords (``image_query``), they are scrubbed again here, and only that
scrubbed text leaves the server.
"""

import re
import time

import httpx

from app.core.errors import APIError

OPENVERSE_URL = "https://api.openverse.org/v1/images/"
MAX_QUERY = 80
CACHE_TTL = 3600
CACHE_MAX = 256
_cache: dict[str, tuple[float, list[dict]]] = {}


def clean_query(text):
    """Keep letters and spaces only: drops numbers, emails, IDs and punctuation."""
    text = re.sub(r"\S+@\S+", " ", text or "")
    text = re.sub(r"[^\w\s]|\d|_", " ", text)
    words = text.split()[:6]
    return " ".join(words)[:MAX_QUERY].strip().lower()


def _item(raw):
    thumbnail = raw.get("thumbnail") or raw.get("url")
    landing = raw.get("foreign_landing_url") or raw.get("url")
    if not thumbnail or not landing or not str(thumbnail).startswith("https://"):
        return None
    license_name = (raw.get("license") or "").upper()
    version = raw.get("license_version") or ""
    return {
        "title": (raw.get("title") or "")[:200],
        "creator": (raw.get("creator") or "")[:120],
        "license": f"CC {license_name} {version}".strip() if license_name else "",
        "license_url": raw.get("license_url") or "",
        "landing_url": landing,
        "thumbnail": thumbnail,
    }


def search(query, limit=4):
    query = clean_query(query)
    if len(query) < 3:
        return []
    now = time.monotonic()
    hit = _cache.get(query)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    try:
        response = httpx.get(
            OPENVERSE_URL,
            params={"q": query, "page_size": limit, "mature": "false"},
            headers={"Accept": "application/json", "User-Agent": "legal-ai-images/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
    except (httpx.HTTPError, ValueError):
        raise APIError(503, "image_search_unavailable", "Image search is unavailable") from None
    images = [item for item in map(_item, results) if item][:limit]
    if len(_cache) >= CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[query] = (now, images)
    return images
