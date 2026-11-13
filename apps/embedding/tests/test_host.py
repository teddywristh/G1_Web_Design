import threading
import time

import numpy as np
from app.main import Runtime, create_app
from fastapi.testclient import TestClient


class Model:
    def encode_query(self, texts, **kwargs):
        return np.tile([3.0, 4.0, 9.0], (len(texts), 1))

    def encode_document(self, texts, **kwargs):
        return np.tile([4.0, 3.0, 9.0], (len(texts), 1))


def client():
    runtime = Runtime()
    runtime.model = Model()
    return TestClient(create_app(runtime)), runtime


def test_truncate_then_normalize_and_prompt_dispatch():
    api, _ = client()
    for kind, expected in [("query", [0.6, 0.8]), ("passage", [0.8, 0.6])]:
        response = api.post(
            "/v1/embeddings",
            json={"input": ["Tiếng Việt", "Luật"], "input_type": kind, "dimensions": 2},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert [x["index"] for x in data] == [0, 1]
        np.testing.assert_allclose(data[0]["embedding"], expected)


def test_errors_and_readiness(monkeypatch):
    api, runtime = client()
    assert api.post("/v1/embeddings", json={"input": " "}).status_code == 422
    assert (
        api.post("/v1/embeddings", json={"input": "abc", "model": "other"}).status_code
        == 400
    )
    runtime.lock.acquire()
    assert api.post("/v1/embeddings", json={"input": "abc"}).status_code == 429
    runtime.lock.release()
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    assert api.post("/v1/embeddings", json={"input": "abc"}).status_code == 401
    runtime.model = None
    assert api.get("/health").json()["model_loaded"] is False
    assert api.get("/ready").status_code == 503
    assert (
        api.post(
            "/v1/embeddings",
            headers={"Authorization": "Bearer test-key"},
            json={"input": "abc"},
        ).status_code
        == 503
    )


def test_body_limit_and_invalid_vectors():
    api, _ = client()
    assert (
        api.post("/v1/embeddings", content=b"x" * (1024 * 1024 + 1)).status_code == 413
    )
    assert (
        api.post("/v1/embeddings", json={"input": "abc", "dimensions": 4}).status_code
        == 503
    )


def post(api, kind):
    return api.post("/v1/embeddings", json={"input": "abc", "input_type": kind, "dimensions": 2})


def test_ingestion_steps_aside_for_a_waiting_question():
    api, runtime = client()
    runtime.waiting_queries = 1
    assert post(api, "passage").status_code == 429  # a question is queued: passages yield
    assert post(api, "query").status_code == 200
    runtime.waiting_queries = 0
    assert post(api, "passage").status_code == 200


def test_a_question_queues_for_the_gpu_instead_of_failing():
    api, runtime = client()
    runtime.query_wait = 5
    runtime.lock.acquire()  # the ingestion worker is mid-inference
    result = {}
    thread = threading.Thread(target=lambda: result.update(code=post(api, "query").status_code))
    thread.start()
    time.sleep(0.2)
    assert thread.is_alive() and runtime.waiting_queries == 1
    assert post(api, "passage").status_code == 429  # and the worker cannot cut the line
    runtime.lock.release()
    thread.join(timeout=5)
    assert result == {"code": 200} and runtime.waiting_queries == 0


def test_a_question_gives_up_after_its_wait():
    api, runtime = client()
    runtime.query_wait = 0.1
    runtime.lock.acquire()
    started = time.monotonic()
    assert post(api, "query").status_code == 429
    assert 0.1 <= time.monotonic() - started < 2 and runtime.waiting_queries == 0
    runtime.lock.release()
