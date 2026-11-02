import json
import subprocess
from unittest.mock import Mock

import pytest

from app.core.config import Settings, get_settings
from app.core.database import get_database
from app.core.errors import APIError
from app.services.opencode import OpenCodeService
from tests.stubs import stub_qa
from tests.test_ai_connections import PERSONAL, configured_crypto, save
from tests.test_backend import api, identity, profile, repo

# Import fixtures used by FastAPI dependency overrides.
__all__ = ["api", "repo", "configured_crypto"]


def test_opencode_route_uses_selected_personal_key_and_existing_citations(
    api, repo, monkeypatch, configured_crypto
):
    client, app, _ = api
    identity(app)
    profile(repo)
    save(repo, {"id": "reader", "role": "user"})
    app.dependency_overrides[get_database] = lambda: Mock()
    monkeypatch.setattr(get_settings(), "opencode_local_enabled", True)
    stub_qa(monkeypatch)
    factory = Mock(return_value=Mock(answer=Mock(return_value="Căn cứ Điều 1.")))
    monkeypatch.setattr("app.api.v1.rag.OpenCodeService", factory)
    result = client.post(
        "/api/v1/rag/ask",
        json={
            "question": "Điều 1 quy định gì?",
            "engine": "opencode",
            "retrieval_mode": "keyword",
            "credential_source": "personal",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["engine"] == "opencode"
    assert result.json()["credential_source"] == "personal"
    assert result.json()["citations"][0]["chunk_id"] == "c"
    assert factory.call_args.args[1] == PERSONAL
    assert PERSONAL not in result.text


@pytest.mark.parametrize(
    "provider,model", [("deepseek", "deepseek-chat"), ("openrouter", "openai/gpt-4o-mini")]
)
def test_opencode_provider_uses_its_own_key_and_model(
    api, repo, monkeypatch, configured_crypto, provider, model
):
    client, app, _ = api
    identity(app)
    profile(repo)
    save(repo, {"id": "reader", "role": "user"}, provider=provider)
    app.dependency_overrides[get_database] = lambda: Mock()
    monkeypatch.setattr(get_settings(), "opencode_local_enabled", True)
    stub_qa(monkeypatch)
    factory = Mock(return_value=Mock(answer=Mock(return_value="Căn cứ Điều 1.")))
    monkeypatch.setattr("app.api.v1.rag.OpenCodeService", factory)
    result = client.post(
        "/api/v1/rag/ask",
        json={
            "question": "Điều 1 quy định gì?",
            "engine": "opencode",
            "provider": provider,
            "model": model,
            "retrieval_mode": "keyword",
            "credential_source": "personal",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["provider"] == provider
    assert factory.call_args.args[1:3] == (PERSONAL, model)
    assert factory.call_args.kwargs["provider"] == provider
    assert PERSONAL not in result.text


def test_opencode_disabled_and_production_configuration_rejected(api, repo, monkeypatch):
    client, app, _ = api
    identity(app)
    profile(repo)
    app.dependency_overrides[get_database] = lambda: Mock()
    monkeypatch.setattr(get_settings(), "opencode_local_enabled", False)
    response = client.post(
        "/api/v1/rag/ask", json={"question": "Câu hỏi pháp luật", "engine": "opencode"}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "opencode_unavailable"
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            app_env="production",
            opencode_local_enabled=True,
            auth_cookie_secure=True,
            firebase_project_id="test-project",
            firebase_storage_bucket="test-bucket",
            firebase_auth_emulator_host=None,
            firestore_emulator_host=None,
            storage_emulator_host=None,
        )


def test_opencode_runner_sends_credential_only_via_stdin_and_cleans_up(monkeypatch, tmp_path):
    binary = tmp_path / "opencode"
    binary.write_text("fake")
    settings = get_settings().model_copy(
        update={"opencode_binary": str(binary), "opencode_image": "fake-image"}
    )
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if command[-1] == "/opt/worker.py":
            return subprocess.CompletedProcess(
                command, 0, stdout=json.dumps({"answer": "Kết quả."}).encode(), stderr=b""
            )
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr("app.services.opencode.subprocess.run", run)
    answer = OpenCodeService(settings, PERSONAL, "test-model").answer("Câu hỏi?", [])
    assert answer == "Kết quả."
    assert all(PERSONAL not in " ".join(command) for command, _ in calls)
    payloads = [kwargs["input"] for _, kwargs in calls if "input" in kwargs]
    assert len(payloads) == 1 and json.loads(payloads[0])["apiKey"] == PERSONAL
    assert any(command[1:3] == ["network", "rm"] for command, _ in calls)
    assert len([command for command, _ in calls if command[1:3] == ["rm", "-f"]]) == 2


def test_opencode_runner_failure_redacts_key_and_cleans_up(monkeypatch, tmp_path):
    binary = tmp_path / "opencode"
    binary.write_text("fake")
    settings = get_settings().model_copy(update={"opencode_binary": str(binary)})
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[-1] == "/opt/worker.py":
            raise subprocess.CalledProcessError(1, command, output=PERSONAL.encode())
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr("app.services.opencode.subprocess.run", run)
    with pytest.raises(APIError) as exc:
        OpenCodeService(settings, PERSONAL, "test-model").answer("Câu hỏi?", [])
    assert exc.value.status == 503 and PERSONAL not in exc.value.message
    assert any(c[1:3] == ["network", "rm"] for c in calls)


@pytest.mark.parametrize(
    ("code", "status"),
    [("ai_authentication_failed", 502), ("ai_rate_limited", 429), ("ai_incomplete", 502)],
)
def test_opencode_runner_maps_safe_worker_errors(monkeypatch, tmp_path, code, status):
    binary = tmp_path / "opencode"
    binary.write_text("fake")
    settings = get_settings().model_copy(update={"opencode_binary": str(binary)})

    def run(command, **kwargs):
        output = json.dumps({"error": code}).encode() if command[-1] == "/opt/worker.py" else b""
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr=b"")

    monkeypatch.setattr("app.services.opencode.subprocess.run", run)
    with pytest.raises(APIError) as exc:
        OpenCodeService(settings, PERSONAL, "test-model").answer("Câu hỏi?", [])
    assert exc.value.status == status
    assert exc.value.code == code
