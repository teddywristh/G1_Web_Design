"""Streaming and per-request effort: adapters, worker plumbing, the SSE endpoint, parallel fetch."""

import json
import subprocess
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.database import get_database
from app.core.errors import APIError
from app.schemas.rag import AskResponse
from app.services import oauth_store, opencode, opencode_oauth, web_sources
from app.services.opencode import OpenCodeService
from tests.memory_repo import MemoryRepo
from tests.stubs import stub_qa
from tests.test_backend import api, identity, profile, repo

__all__ = ["api", "repo"]

CREDENTIAL = {"type": "oauth", "access": "a", "refresh": "r1"}


@pytest.fixture
def settings():
    return Settings(ai_credential_encryption_key=SecretStr(Fernet.generate_key().decode()))


class FakeProc:
    """Stands in for a `docker run/exec` child whose stdout is already known."""

    def __init__(self, lines, code=0):
        self.sent = b""
        self.stdin = SimpleNamespace(write=self._write, close=lambda: None)
        self.stdout = iter(lines)
        self.returncode = code

    def _write(self, data):
        self.sent += data

    def poll(self):
        return self.returncode

    def kill(self):
        pass

    def wait(self, timeout=None):
        return self.returncode


def ndjson(*lines):
    return [json.dumps(line, ensure_ascii=False).encode() + b"\n" for line in lines]


# --- ChatGPT (OAuth) adapter ---------------------------------------------------------------


def oauth_answer(settings, monkeypatch, repo=None):
    session = {"lock": threading.Lock(), "connected": True}
    get = Mock(return_value=session)
    monkeypatch.setattr(opencode_oauth, "get", get)
    return opencode_oauth.OAuthAnswer("alice", "m", repo or MemoryRepo(), settings), session, get


def test_answer_is_one_worker_call_and_unchanged_credentials_are_not_rewritten(
    settings, monkeypatch
):
    repo = MemoryRepo()
    answer, session, get = oauth_answer(settings, monkeypatch, repo)
    invoke = Mock(return_value={"answer": "ok", "credential": CREDENTIAL})
    monkeypatch.setattr(opencode_oauth, "invoke", invoke)
    save = Mock(wraps=oauth_store.save)
    monkeypatch.setattr(oauth_store, "save", save)
    answer.require_session()
    assert answer.answer("q", [], effort="low") == "ok"
    assert answer.answer("q", []) == "ok"
    assert get.call_count == 1  # the worker was checked once for the request, not per call
    sent = [call.args[1] for call in invoke.call_args_list]
    assert [p["action"] for p in sent] == ["answer", "answer"]  # no separate export call
    assert sent[0]["variant"] == "low" and "variant" not in sent[1]
    assert save.call_count == 1
    invoke.return_value = {"answer": "ok", "credential": {**CREDENTIAL, "refresh": "r2"}}
    answer.answer("q", [])
    assert save.call_count == 2
    assert oauth_store.load(repo, settings, "alice")["refresh"] == "r2"


def test_an_unknown_effort_is_not_sent(settings, monkeypatch):
    answer, _, _ = oauth_answer(settings, monkeypatch)
    assert "variant" not in answer.payload("q", [], "extreme", False)


def test_the_session_is_checked_again_after_a_while(settings, monkeypatch):
    answer, _, get = oauth_answer(settings, monkeypatch)
    monkeypatch.setattr(opencode_oauth, "invoke", Mock(return_value={"answer": "ok"}))
    monkeypatch.setattr(answer, "persist", Mock())
    answer.require_session()
    clock = [time.monotonic() + opencode_oauth.SESSION_CHECK_SECONDS + 1]
    monkeypatch.setattr(opencode_oauth.time, "monotonic", lambda: clock[0])
    answer.answer("q", [])
    assert get.call_count == 2


def test_a_worker_without_the_combined_call_still_gets_its_credential_exported(
    settings, monkeypatch
):
    repo = MemoryRepo()
    answer, _, _ = oauth_answer(settings, monkeypatch, repo)
    invoke = Mock(side_effect=[{"answer": "ok"}, {"credential": CREDENTIAL}])
    monkeypatch.setattr(opencode_oauth, "invoke", invoke)
    assert answer.answer("q", []) == "ok"
    assert [c.args[1]["action"] for c in invoke.call_args_list] == ["answer", "export"]
    assert oauth_store.load(repo, settings, "alice") == CREDENTIAL


def test_provider_errors_keep_the_rotated_credential(settings, monkeypatch):
    repo = MemoryRepo()
    answer, _, _ = oauth_answer(settings, monkeypatch, repo)
    monkeypatch.setattr(
        opencode_oauth,
        "invoke",
        Mock(return_value={"error": "ai_rate_limited", "credential": CREDENTIAL}),
    )
    with pytest.raises(APIError) as caught:
        answer.answer("q", [])
    assert caught.value.status == 429
    assert oauth_store.load(repo, settings, "alice") == CREDENTIAL


def test_stream_yields_deltas_then_only_the_tail_that_was_not_streamed(settings, monkeypatch):
    repo = MemoryRepo()
    answer, _, _ = oauth_answer(settings, monkeypatch, repo)
    seen = []

    def lines(session, payload, timeout):
        seen.append(payload)
        yield {"delta": "Xin "}
        yield {"delta": "chào"}
        yield {"answer": "Xin chào bạn", "credential": CREDENTIAL}

    monkeypatch.setattr(opencode_oauth, "invoke_stream", lines)
    assert list(answer.answer_stream("q", [], effort="low")) == ["Xin ", "chào", " bạn"]
    assert seen[0]["stream"] is True and seen[0]["variant"] == "low"
    assert oauth_store.load(repo, settings, "alice") == CREDENTIAL


@pytest.mark.parametrize(
    ("final", "status"),
    [({"error": "ai_incomplete"}, 502), ({"error": "ai_rate_limited"}, 429), (None, 503)],
)
def test_stream_failures_map_to_safe_errors(settings, monkeypatch, final, status):
    answer, _, _ = oauth_answer(settings, monkeypatch)
    # Saving the credential fails too; the provider's own error must still be what the caller sees.
    monkeypatch.setattr(
        opencode_oauth, "invoke", Mock(side_effect=APIError(503, "opencode_unavailable", "x"))
    )

    def lines(*_):
        yield {"delta": "Xin "}
        if final:
            yield final

    monkeypatch.setattr(opencode_oauth, "invoke_stream", lines)
    chunks = []
    with pytest.raises(APIError) as caught:
        for piece in answer.answer_stream("q", []):
            chunks.append(piece)
    assert caught.value.status == status and chunks == ["Xin "]


def test_invoke_stream_reads_the_workers_lines_as_they_arrive(monkeypatch):
    proc = FakeProc(ndjson({"delta": "a"}, {"answer": "a"}))
    popen = Mock(return_value=proc)
    monkeypatch.setattr(opencode_oauth.subprocess, "Popen", popen)
    session = {"worker": "w"}
    got = list(opencode_oauth.invoke_stream(session, {"action": "answer"}, 5))
    assert got == [{"delta": "a"}, {"answer": "a"}]
    assert popen.call_args.args[0] == ["docker", "exec", "-i", "w", "python", "/opt/oauth_call.py"]
    assert json.loads(proc.sent) == {"action": "answer"}


@pytest.mark.parametrize(("running", "status"), [(b"true", 503), (b"false", 409)])
def test_invoke_stream_failure_tells_a_dead_worker_from_a_failed_call(monkeypatch, running, status):
    monkeypatch.setattr(opencode_oauth.subprocess, "Popen", Mock(return_value=FakeProc([], code=1)))
    monkeypatch.setattr(opencode_oauth, "docker", Mock(return_value=Mock(stdout=running)))
    monkeypatch.setattr(opencode_oauth, "cleanup", Mock())
    monkeypatch.setattr(opencode_oauth, "SESSIONS", {})
    with pytest.raises(APIError) as caught:
        list(opencode_oauth.invoke_stream({"worker": "w"}, {}, 5))
    assert caught.value.status == status


# --- API-key adapter -----------------------------------------------------------------------


@pytest.fixture
def sandbox(monkeypatch, tmp_path):
    binary = tmp_path / "opencode"
    binary.write_text("fake")
    docker = []

    def run(command, **kwargs):
        docker.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(opencode.subprocess, "run", run)
    config = get_settings().model_copy(update={"opencode_binary": str(binary)})
    return config, docker


def test_api_key_stream_passes_effort_and_yields_deltas(sandbox, monkeypatch):
    config, docker = sandbox
    proc = FakeProc(ndjson({"delta": "Xin "}, {"delta": "chào"}, {"answer": "Xin chào bạn"}))
    popen = Mock(return_value=proc)
    monkeypatch.setattr(opencode.subprocess, "Popen", popen)
    service = OpenCodeService(config, "sk-test-key-not-real", "gpt-5.6-luna")
    assert list(service.answer_stream("q?", [], effort="low")) == ["Xin ", "chào", " bạn"]
    command = popen.call_args.args[0]
    assert command[:4] == ["docker", "run", "--rm", "-i"] and command[-1] == "/opt/worker.py"
    job = json.loads(proc.sent)
    assert job["stream"] is True and job["variant"] == "low"
    assert job["apiKey"] == "sk-test-key-not-real"
    assert all("sk-test-key-not-real" not in " ".join(c) for c, _ in docker)
    assert any(c[1:3] == ["network", "rm"] for c, _ in docker)  # the sandbox is removed


def test_api_key_stream_reports_worker_errors_safely(sandbox, monkeypatch):
    config, docker = sandbox
    monkeypatch.setattr(
        opencode.subprocess,
        "Popen",
        Mock(return_value=FakeProc(ndjson({"error": "ai_authentication_failed"}))),
    )
    with pytest.raises(APIError) as caught:
        list(OpenCodeService(config, "sk-x", "m").answer_stream("q", []))
    assert caught.value.code == "ai_authentication_failed"
    assert any(c[1:3] == ["network", "rm"] for c, _ in docker)


def test_api_key_stream_without_a_final_line_is_unavailable(sandbox, monkeypatch):
    config, _ = sandbox
    monkeypatch.setattr(
        opencode.subprocess, "Popen", Mock(return_value=FakeProc(ndjson({"delta": "x"})))
    )
    with pytest.raises(APIError) as caught:
        list(OpenCodeService(config, "sk-x", "m").answer_stream("q", []))
    assert caught.value.status == 503


def test_api_key_answer_sends_the_effort_variant(sandbox, monkeypatch):
    config, docker = sandbox

    def run(command, **kwargs):
        docker.append((command, kwargs))
        out = json.dumps({"answer": "ok"}).encode() if command[-1] == "/opt/worker.py" else b""
        return subprocess.CompletedProcess(command, 0, stdout=out, stderr=b"")

    monkeypatch.setattr(opencode.subprocess, "run", run)
    service = OpenCodeService(config, "sk-x", "m")
    assert service.answer("q", [], effort="minimal") == "ok"
    assert service.answer("q", [], effort="bogus") == "ok"
    jobs = [json.loads(kw["input"]) for _, kw in docker if "input" in kw]
    assert jobs[0]["variant"] == "minimal" and "variant" not in jobs[1]


# --- /rag/ask/stream -----------------------------------------------------------------------


def chat_payload(**extra):
    return {
        "question": "Câu hỏi mẫu",
        "engine": "opencode",
        "provider": "openai",
        "credential_source": "chatgpt",
        "retrieval_mode": "keyword",
        "model": "gpt-5.6-luna",
        **extra,
    }


@pytest.fixture
def client(api, repo, monkeypatch):
    client, app, _ = api
    identity(app)
    profile(repo)
    app.dependency_overrides[get_database] = lambda: Mock()
    config = get_settings()
    monkeypatch.setattr(config, "opencode_local_enabled", True)
    monkeypatch.setattr(config, "opencode_chatgpt_local_enabled", True)
    monkeypatch.setattr("app.api.v1.rag.OAuthAnswer", Mock(return_value=Mock()))
    return client


def events_of(body):
    events = []
    for block in body.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        assert name == "event: " + json.loads(data[len("data: ") :])["type"]
        events.append(json.loads(data[len("data: ") :]))
    return events


FINAL = AskResponse(
    answer="A [1]",
    citations=[],
    retrieved_chunks=[],
    has_sufficient_evidence=True,
    status="answered",
)


def test_stream_endpoint_sends_events_and_an_annotated_final_response(client, monkeypatch):
    calls = []

    def fake(repo, user, request, ai, embedder, settings, **kwargs):
        calls.append(kwargs)
        yield {"type": "stage", "stage": "retrieving"}
        yield {"type": "claim", "text": "A [1]", "citations": []}
        yield {"type": "done", "response": FINAL}

    monkeypatch.setattr("app.api.v1.rag.qa.answer_events", fake)
    response = client.post("/api/v1/rag/ask/stream", json=chat_payload())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["cache-control"] == "no-store"
    events = events_of(response.text)
    assert [e["type"] for e in events] == ["stage", "claim", "done"]
    done = events[-1]["response"]
    assert done["answer"] == "A [1]" and done["status"] == "answered"
    assert (done["provider"], done["credential_source"], done["engine"]) == (
        "openai",
        "chatgpt",
        "opencode",
    )
    assert calls[0]["stream"] is True and calls[0]["scope"] is not None
    assert isinstance(calls[0]["request_id"], str)


@pytest.mark.parametrize(
    ("failure", "code", "status"),
    [
        (APIError(502, "ai_authentication_failed", "rejected"), "ai_authentication_failed", 502),
        (RuntimeError("sk-secret-token"), "ai_not_configured", 503),
        (type("E", (Exception,), {"status_code": 429})("sk-secret-token"), "ai_rate_limited", 429),
        (ValueError("sk-secret-token"), "ai_unavailable", 503),
    ],
)
def test_a_failure_while_streaming_becomes_one_safe_error_event(
    client, monkeypatch, failure, code, status
):
    def fake(*_, **__):
        yield {"type": "stage", "stage": "retrieving"}
        raise failure

    monkeypatch.setattr("app.api.v1.rag.qa.answer_events", fake)
    response = client.post("/api/v1/rag/ask/stream", json=chat_payload())
    assert response.status_code == 200
    events = events_of(response.text)
    assert [e["type"] for e in events] == ["stage", "error"]
    assert (events[-1]["code"], events[-1]["status"]) == (code, status)
    assert "sk-secret-token" not in response.text


def test_errors_before_the_stream_starts_are_ordinary_http_errors(client, monkeypatch):
    response = client.post("/api/v1/rag/ask/stream", json=chat_payload(provider="anthropic"))
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_provider"
    monkeypatch.setattr(get_settings(), "qa_workflow_enabled", False)
    response = client.post("/api/v1/rag/ask/stream", json=chat_payload())
    assert response.status_code == 503 and response.headers["content-type"].startswith(
        "application/json"
    )


def test_stream_endpoint_requires_a_login(api):
    client, _, _ = api
    assert client.post("/api/v1/rag/ask/stream", json=chat_payload()).status_code == 401


def test_json_endpoint_hands_the_scope_and_request_id_to_the_workflow(client, monkeypatch):
    stub = stub_qa(monkeypatch)
    response = client.post("/api/v1/rag/ask", json=chat_payload())
    assert response.status_code == 200
    kwargs = stub.call_args.kwargs
    assert kwargs["scope"] is not None and isinstance(kwargs["request_id"], str)


# --- parallel web fetch --------------------------------------------------------------------


def congbao_handler(delay, broken=()):
    def handler(request):
        if request.method == "POST":
            documents = [
                {
                    "type": "van_ban",
                    "data": {
                        "danh_sach_tep_van_ban": [
                            {
                                "file_extension": "pdf",
                                "duong_dan": f"https://congbaocdn.chinhphu.vn/{n}.pdf",
                            }
                            for n in range(3)
                        ]
                    },
                }
            ]
            return httpx.Response(200, json={"success": True, "data": documents})
        time.sleep(delay)
        n = request.url.path.strip("/").split(".")[0]
        if n in broken:
            return httpx.Response(404, text="gone", headers={"content-type": "text/html"})
        body = f"<p>Điều 1. Nguồn {n}</p><p>Điều 2. B</p><p>Điều 3. C</p>"
        return httpx.Response(200, text=body, headers={"content-type": "text/html"})

    return handler


def gather(handler):
    config = Settings(official_web_enabled=True, max_fetched_sources=3)
    budget = {"searches": 0, "fetches": 0}
    started = time.perf_counter()
    result = web_sources.gather(
        SimpleNamespace(client=None),
        config,
        "Mức phạt",
        "official",
        budget,
        httpx.MockTransport(handler),
    )
    return result, budget, time.perf_counter() - started


def test_sources_are_fetched_together_and_keep_search_order():
    (items, notes), budget, elapsed = gather(congbao_handler(0.4))
    assert [i["sourceUrl"][-5:] for i in items] == ["0.pdf", "1.pdf", "2.pdf"]
    assert not notes and budget["fetches"] == 3
    assert elapsed < 0.9  # three 0.4s fetches one after another would take 1.2s


def test_one_unreadable_source_does_not_lose_the_others():
    (items, notes), _, _ = gather(congbao_handler(0, broken=("1",)))
    assert [i["sourceUrl"][-5:] for i in items] == ["0.pdf", "2.pdf"]
    assert notes == ["web_source_unreadable"]
