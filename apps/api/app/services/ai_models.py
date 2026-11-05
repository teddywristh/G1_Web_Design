"""Models each configured connection can use, grouped for a single provider/model picker."""

import hashlib
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.core.errors import APIError
from app.services import opencode_oauth
from app.services.ai_connections import resolve
from app.services.opencode import worker_access

PROVIDERS = ("openai", "anthropic", "deepseek", "openrouter")
LABELS = {
    "openai": "OpenAI",
    "anthropic": "Claude (Anthropic)",
    "deepseek": "DeepSeek",
    "openrouter": "OpenRouter",
}
# Same shape AskRequest.model accepts; anything else could never be selected.
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$")
MAX_MODELS = 500
CACHE_SECONDS = 600
CACHE = {}
LOCK = threading.Lock()
OPENAI_CHAT = re.compile(r"^(gpt-|chatgpt-|o\d|codex)")
OPENAI_EXCLUDED = (
    "audio",
    "dall-e",
    "embedding",
    "image",
    "instruct",
    "moderation",
    "realtime",
    "search",
    "transcribe",
    "tts",
    "whisper",
)


def clean(items):
    models, seen = [], set()
    for model_id, name in items:
        if (
            isinstance(model_id, str)
            and len(model_id) <= 200
            and MODEL_ID.match(model_id)
            and model_id not in seen
        ):
            seen.add(model_id)
            models.append({"id": model_id, "name": name if isinstance(name, str) else model_id})
    return models[:MAX_MODELS]


def fetch(provider, api_key, settings, transport=None):
    headers = {"Authorization": f"Bearer {api_key}"}
    url = {
        "openai": "https://api.openai.com/v1/models",
        "anthropic": "https://api.anthropic.com/v1/models?limit=1000",
        "deepseek": "https://api.deepseek.com/models",
        "openrouter": "https://openrouter.ai/api/v1/models",
    }[provider]
    if provider == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": settings.anthropic_api_version}
    try:
        with httpx.Client(
            timeout=min(settings.ai_request_timeout_seconds, 15),
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.get(url, headers=headers)
        if response.status_code in (401, 403):
            raise APIError(502, "ai_authentication_failed", "The AI provider rejected the key")
        if response.status_code == 429:
            raise APIError(429, "ai_rate_limited", "The AI provider usage limit was reached")
        if response.status_code >= 400:
            raise APIError(502, "ai_provider_error", "The AI provider could not list models")
        data = response.json().get("data") or []
    except (httpx.HTTPError, ValueError, AttributeError):
        raise APIError(503, "ai_unavailable", "The AI provider is unavailable") from None
    if provider == "openai":
        data = sorted(
            (
                item
                for item in data
                if OPENAI_CHAT.match(str(item.get("id", "")))
                and not any(word in str(item.get("id")) for word in OPENAI_EXCLUDED)
            ),
            key=lambda item: item.get("created") or 0,
            reverse=True,
        )
        return clean((item.get("id"), item.get("id")) for item in data)
    if provider == "anthropic":
        return clean((item.get("id"), item.get("display_name")) for item in data)
    if provider == "openrouter":
        data = [
            item
            for item in data
            if "text" in ((item.get("architecture") or {}).get("output_modalities") or ["text"])
        ]
        return clean((item.get("id"), item.get("name")) for item in data)
    return clean((item.get("id"), item.get("id")) for item in data)


def cached(provider, api_key, settings):
    # Keyed by a digest so cache entries never hold or reveal the credential itself.
    key = hashlib.sha256(f"{provider}\0{api_key}".encode()).hexdigest()
    now = time.monotonic()
    with LOCK:
        hit = CACHE.get(key)
        if hit and hit[0] > now:
            return hit[1]
    models = fetch(provider, api_key, settings)
    with LOCK:
        for stale in [item for item, value in CACHE.items() if value[0] <= now]:
            CACHE.pop(stale, None)
        CACHE[key] = (now + CACHE_SECONDS, models)
    return models


def group(group_id, provider, source, label, load):
    try:
        return {
            "id": group_id,
            "provider": provider,
            "source": source,
            "label": label,
            "models": load(),
            "error": None,
        }
    except APIError as error:
        return {
            "id": group_id,
            "provider": provider,
            "source": source,
            "label": label,
            "models": [],
            "error": error.code,
        }


def allowed(settings, client_host, *, chatgpt):
    try:
        worker_access(settings, client_host, chatgpt=chatgpt)
    except APIError:
        return False
    return bool(settings.opencode_binary)


def list_models(repo, user, settings, client_host):
    jobs = []
    chatgpt = allowed(settings, client_host, chatgpt=True)
    if chatgpt:
        try:
            session = opencode_oauth.get(user["id"], repo, settings)
            chatgpt = bool(session and session["connected"])
        except APIError:
            pass  # Keep the group so the picker can show the restore failure.
    if chatgpt:
        jobs.append(
            (
                "chatgpt",
                "openai",
                "chatgpt",
                "ChatGPT",
                lambda: clean(
                    (item.get("id"), item.get("name"))
                    for item in opencode_oauth.models(user["id"], repo, settings)
                    if isinstance(item, dict)
                ),
            )
        )
    api_keys = allowed(settings, client_host, chatgpt=False)
    for provider in PROVIDERS if api_keys else ():
        try:
            credential = resolve(repo, user, provider, "auto", settings)
        except APIError:
            continue
        jobs.append(
            (
                provider,
                provider,
                credential.source,
                LABELS[provider],
                lambda credential=credential: cached(
                    credential.provider, credential.api_key, settings
                ),
            )
        )
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        groups = list(pool.map(lambda job: group(*job), jobs))
    return {"groups": groups, "apiKeysAvailable": api_keys}
