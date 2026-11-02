"""Private encrypted BYOK credentials and explicitly selected shared credentials."""

import hashlib
import json
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import APIError
from app.schemas.ai_connections import ConnectionOut

COLLECTION = "ai_connections"


@dataclass(repr=False)
class Credential:
    provider: str
    api_key: str
    source: str


def connection_id(owner, provider):
    return hashlib.sha256(json.dumps([owner, provider]).encode()).hexdigest()


def cipher(settings):
    secret = settings.ai_credential_encryption_key.get_secret_value()
    if not secret:
        raise APIError(
            503, "credential_storage_unavailable", "AI credential storage is not configured"
        )
    try:
        return Fernet(secret.encode())
    except (ValueError, TypeError):
        raise APIError(
            503, "credential_storage_unavailable", "AI credential encryption is unavailable"
        ) from None


def owner_for(user, shared):
    if shared:
        if user["role"] != "admin":
            raise APIError(403, "forbidden", "Admin permission required")
        return "system"
    return "user:" + user["id"]


def environment_key(provider, settings):
    return settings.openai_api_key if provider == "openai" else settings.anthropic_api_key


def status(repo, owner, provider, settings):
    row = repo.get(COLLECTION, connection_id(owner, provider))
    shared = owner == "system"
    env = bool(environment_key(provider, settings)) if shared and row is None else False
    configured = bool((row or {}).get("encryptedCredential")) or env
    enabled = (row or {}).get("enabled", env) and configured
    if shared:
        enabled = enabled and settings.ai_allow_shared_keys
    return ConnectionOut(
        provider=provider,
        scope="shared" if shared else "personal",
        configured=configured,
        enabled=enabled,
        version=(row or {}).get("version", 0),
        origin="stored" if row else ("environment" if env else "none"),
    )


def save(repo, user, provider, body, settings, request_id, *, shared=False):
    owner = owner_for(user, shared)
    # Bind the ciphertext to its owner/provider; copying it to another record cannot reassign it.
    encrypted = (
        cipher(settings)
        .encrypt(
            json.dumps(
                {
                    "owner": owner,
                    "provider": provider,
                    "apiKey": body.apiKey.get_secret_value(),
                }
            ).encode()
        )
        .decode()
    )

    def change(current):
        if (current or {}).get("version", 0) != body.expectedVersion:
            raise APIError(409, "version_conflict", "Connection changed; reload before retrying")
        return {
            "ownerId": owner,
            "provider": provider,
            "authType": "api_key",
            "encryptedCredential": encrypted,
            "enabled": body.enabled,
        }

    repo.mutate(
        COLLECTION,
        connection_id(owner, provider),
        change,
        actor=user["id"],
        event="ai.connection_saved",
        request_id=request_id,
    )
    return status(repo, owner, provider, settings)


def remove(repo, user, provider, version, settings, request_id, *, shared=False):
    owner = owner_for(user, shared)

    def change(current):
        if not current:
            raise APIError(404, "not_found", "Stored connection not found")
        if current.get("version") != version:
            raise APIError(409, "version_conflict", "Connection changed; reload before retrying")
        return {"encryptedCredential": None, "enabled": False}

    repo.mutate(
        COLLECTION,
        connection_id(owner, provider),
        change,
        actor=user["id"],
        event="ai.connection_removed",
        request_id=request_id,
    )
    return status(repo, owner, provider, settings)


def from_record(row, owner, provider, settings):
    if not row or not row.get("enabled") or not row.get("encryptedCredential"):
        return None
    try:
        value = json.loads(cipher(settings).decrypt(row["encryptedCredential"].encode()))
        if value["owner"] != owner or value["provider"] != provider or not value["apiKey"]:
            raise ValueError()
        return Credential(provider, value["apiKey"], "shared" if owner == "system" else "personal")
    except (InvalidToken, ValueError, TypeError, KeyError):
        raise APIError(
            503, "credential_unavailable", "Stored AI credential cannot be read"
        ) from None


def resolve(repo, user, provider, source, settings):
    """Auto prefers a personal key. Provider rejection never triggers a billing fallback."""
    owner = "user:" + user["id"]
    if source in {"auto", "personal"}:
        row = repo.get(COLLECTION, connection_id(owner, provider))
        personal = from_record(row, owner, provider, settings)
        if personal:
            return personal
        if source == "personal":
            raise APIError(
                503, "ai_not_configured", "Configure a personal API key for this provider"
            )
    if settings.ai_allow_shared_keys and source in {"auto", "shared"}:
        row = repo.get(COLLECTION, connection_id("system", provider))
        shared = from_record(row, "system", provider, settings)
        if shared:
            return shared
        # An explicit tombstone/disabled stored record suppresses environment fallback.
        key = environment_key(provider, settings) if row is None else ""
        if key:
            return Credential(provider, key, "shared")
    raise APIError(503, "ai_not_configured", "No enabled API key is available for this provider")


def options(repo, user, settings):
    storage_ready = True
    try:
        cipher(settings)
    except APIError:
        storage_ready = False
    return {
        "credentialStorageReady": storage_ready,
        "connections": [
            status(repo, owner, provider, settings).model_dump()
            for owner in ("user:" + user["id"], "system")
            for provider in ("openai", "anthropic")
        ],
        "methods": [
            {"id": "api_key", "provider": "openai", "available": True, "reason": "OpenAI API key"},
            {
                "id": "api_key",
                "provider": "anthropic",
                "available": True,
                "reason": "Anthropic API key",
            },
            {
                "id": "chatgpt_oauth",
                "provider": "openai",
                "available": False,
                "reason": "Hosted ChatGPT plan usage requires OpenAI integration access",
                "documentationUrl": "https://developers.openai.com/siwc/token-sharing-open-source",
            },
            {
                "id": "claude_pro_oauth",
                "provider": "anthropic",
                "available": False,
                "reason": "Claude Pro login is not supported for third-party inference apps",
                "documentationUrl": "https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use",
            },
        ],
    }
