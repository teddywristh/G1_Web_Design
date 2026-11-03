"""Encrypted, per-user OpenCode credentials; plaintext never leaves the backend."""

import hashlib
import json

from cryptography.fernet import InvalidToken

from app.core.errors import APIError
from app.services.ai_connections import cipher

COLLECTION = "chatgpt_oauth_connections"


def key_for(user_id):
    return hashlib.sha256(("chatgpt:" + user_id).encode()).hexdigest()


def save(repo, settings, user_id, credential):
    if not isinstance(credential, dict) or credential.get("type") != "oauth":
        raise APIError(503, "credential_unavailable", "ChatGPT credentials are unavailable")
    encrypted = (
        cipher(settings)
        .encrypt(
            json.dumps({"owner": user_id, "credential": credential}, separators=(",", ":")).encode()
        )
        .decode()
    )
    repo.mutate(
        COLLECTION,
        key_for(user_id),
        lambda _: {"ownerId": user_id, "encryptedCredential": encrypted},
        actor=user_id,
        event="chatgpt.credential_saved",
        request_id="oauth",
    )


def load(repo, settings, user_id):
    row = repo.get(COLLECTION, key_for(user_id))
    if not row or not row.get("encryptedCredential"):
        return None
    try:
        payload = json.loads(cipher(settings).decrypt(row["encryptedCredential"].encode()))
        if payload.get("owner") != user_id or payload["credential"].get("type") != "oauth":
            raise ValueError()
        return payload["credential"]
    except (InvalidToken, ValueError, TypeError, KeyError):
        raise APIError(
            503, "credential_unavailable", "Stored ChatGPT connection cannot be read"
        ) from None


def remove(repo, user_id):
    repo.mutate(
        COLLECTION,
        key_for(user_id),
        lambda current: {"encryptedCredential": None} if current else None,
        actor=user_id,
        event="chatgpt.credential_removed",
        request_id="oauth",
    )
