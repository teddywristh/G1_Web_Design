import threading
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core.config import Settings
from app.core.errors import APIError
from app.services import oauth_store, opencode_oauth
from tests.memory_repo import MemoryRepo


@pytest.fixture
def settings():
    return Settings(ai_credential_encryption_key=SecretStr(Fernet.generate_key().decode()))


def test_credentials_encrypted_bound_to_user_and_removed(settings):
    repo = MemoryRepo()
    credential = {"type": "oauth", "access": "fake-access", "refresh": "fake-refresh"}
    oauth_store.save(repo, settings, "alice", credential)
    row = repo.get(oauth_store.COLLECTION, oauth_store.key_for("alice"))
    assert "fake-access" not in str(row) and "fake-refresh" not in str(row)
    assert oauth_store.load(repo, settings, "alice") == credential
    repo.mutate(
        oauth_store.COLLECTION,
        oauth_store.key_for("bob"),
        lambda _: row,
        actor="test",
        event="test",
        request_id="test",
    )
    with pytest.raises(APIError):
        oauth_store.load(repo, settings, "bob")
    oauth_store.remove(repo, "alice")
    assert oauth_store.load(repo, settings, "alice") is None


def test_worker_restored_from_encrypted_connection(settings, monkeypatch):
    repo = MemoryRepo()
    credential = {"type": "oauth", "access": "fake-access", "refresh": "fake-refresh"}
    oauth_store.save(repo, settings, "alice", credential)
    sessions = {}
    monkeypatch.setattr(opencode_oauth, "SESSIONS", sessions)
    monkeypatch.setattr(opencode_oauth, "docker", Mock(return_value=Mock(stdout=b"true\n")))

    def start(user_id, _settings, credential=None):
        assert credential == {"type": "oauth", "access": "fake-access", "refresh": "fake-refresh"}
        sessions[user_id] = {"expires": float("inf"), "worker": "w", "connected": True}

    monkeypatch.setattr(opencode_oauth, "start", start)
    assert opencode_oauth.get("alice", repo, settings)["connected"]
    assert opencode_oauth.get("bob", repo, settings) is None


def test_answer_saves_rotated_credential(settings, monkeypatch):
    repo = MemoryRepo()
    session = {"lock": threading.Lock(), "connected": True}
    monkeypatch.setattr(opencode_oauth, "get", lambda *_: session)
    monkeypatch.setattr(
        opencode_oauth,
        "invoke",
        Mock(
            side_effect=[
                {"answer": "test answer"},
                {"credential": {"type": "oauth", "refresh": "rotated"}},
            ]
        ),
    )
    answer = opencode_oauth.OAuthAnswer("alice", "test", repo, settings)
    assert answer.answer("question", []) == "test answer"
    assert oauth_store.load(repo, settings, "alice")["refresh"] == "rotated"


def test_successful_login_saves_credentials(settings, monkeypatch):
    repo = MemoryRepo()
    session = {"lock": threading.Lock(), "connected": False}
    monkeypatch.setattr(opencode_oauth, "get", lambda *_: session)
    monkeypatch.setattr(
        opencode_oauth,
        "invoke",
        Mock(
            side_effect=[{"connected": True}, {"credential": {"type": "oauth", "refresh": "fake"}}]
        ),
    )
    assert opencode_oauth.finish("alice", repo, settings) == {"connected": True}
    assert oauth_store.load(repo, settings, "alice")["refresh"] == "fake"


def test_disconnect_deletes_saved_credentials(settings, monkeypatch):
    repo = MemoryRepo()
    oauth_store.save(repo, settings, "alice", {"type": "oauth", "refresh": "fake"})
    session = {"lock": threading.Lock()}
    monkeypatch.setattr(opencode_oauth, "SESSIONS", {"alice": session})
    cleanup = Mock()
    monkeypatch.setattr(opencode_oauth, "cleanup", cleanup)
    opencode_oauth.disconnect("alice", repo)
    assert oauth_store.load(repo, settings, "alice") is None
    assert "alice" not in opencode_oauth.SESSIONS
    cleanup.assert_called_once_with(session)
