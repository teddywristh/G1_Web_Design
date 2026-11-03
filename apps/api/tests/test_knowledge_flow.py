import hashlib
import json
from datetime import date, datetime, timezone

import pytest
from app.core.config import Settings
from app.core.errors import APIError
from app.ingestion import parser, pipeline
from app.schemas.knowledge import EvidenceOut
from app.schemas.rag import AskRequest
from app.services import documents, evidence, knowledge, qa, users
from app.workers import ingestion as worker

from tests.memory_repo import FakeBucket, MemoryRepo

PAGES = [
    "LUẬT MẪU\nChương I\nĐiều 1. Phạm vi\nLuật này quy định về hợp đồng lao động mẫu.\n"
    "Điều 2. Thử việc\n1. Thời gian thử việc tối đa là 60 ngày.\n2. Lương thử việc theo thỏa thuận."
]
SETTINGS = Settings(embedding_dimensions=3)


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeAI:
    client = None

    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def answer(self, question, chunks):
        self.calls += 1
        return self.reply(chunks) if callable(self.reply) else self.reply


@pytest.fixture
def env(monkeypatch):
    repo, bucket = MemoryRepo(), FakeBucket()
    for uid in ("alice", "bob"):
        users.bootstrap(repo, {"uid": uid}, "t")
    monkeypatch.setattr(parser, "extract_pages", lambda *_: PAGES)
    monkeypatch.setattr(worker, "make_embedder", lambda *_: FakeEmbedder())
    return repo, bucket


def user(repo, uid):
    return repo.get("users", uid)


def upload(repo, bucket, tmp_path, uid="alice", content=b"%PDF-1 test"):
    kb = knowledge.create_kb(repo, user(repo, uid), "Kho", "t", SETTINGS)
    doc = knowledge.create_document(
        repo, user(repo, uid), kb["id"], {"displayTitle": "Luật mẫu"}, "t"
    )
    path = tmp_path / "upload.pdf"
    path.write_bytes(content)
    options = knowledge.upload_options(user(repo, uid), kb["id"], doc["id"], "auto", SETTINGS)
    documents.upload_document(
        repo,
        bucket,
        doc["id"],
        str(path),
        len(content),
        hashlib.sha256(content).hexdigest(),
        uid,
        "t",
        doc["version"],
        **options,
    )
    return kb, repo.get("knowledge_documents", doc["id"])


def process(repo, bucket):
    return worker.run_once(repo, bucket, SETTINGS, "w1")


def ask(repo, who, kb_ids, ai, question="Điều 2 thử việc bao lâu?"):
    request = AskRequest(question=question, knowledge_base_ids=kb_ids)
    return qa.answer(repo, user(repo, who), request, ai, FakeEmbedder(), SETTINGS)


def good_reply(chunks):
    key = next(c.text[1 : c.text.index("]")] for c in chunks if "60 ngày" in c.text)
    return json.dumps(
        {
            "status": "answered",
            "claims": [
                {
                    "claim_id": "c1",
                    "kind": "legal_rule",
                    "text": "Thử việc tối đa 60 ngày.",
                    "evidence_ids": [key],
                    "quote": "tối đa là 60 ngày",
                }
            ],
        }
    )


def test_upload_creates_one_job_and_processing_reaches_ready(env, tmp_path):
    repo, bucket = env
    kb, doc = upload(repo, bucket, tmp_path)
    jobs = repo.query("processing_jobs")
    assert len(jobs) == 1 and jobs[0]["status"] == "queued"
    assert knowledge.processing(repo, doc, SETTINGS)["status"] == "queued"
    job = process(repo, bucket)
    assert job["status"] == "succeeded"
    assert knowledge.processing(repo, doc, SETTINGS)["status"] == "ready"
    kb = repo.get("knowledge_bases", kb["id"])
    assert kb["activeIndexGeneration"] == kb["latestGeneration"]
    assert process(repo, bucket) is None


def test_parsed_document_is_searchable_while_embedding_waits(env, tmp_path, monkeypatch):
    repo, bucket = env
    kb, doc = upload(repo, bucket, tmp_path)
    monkeypatch.setattr(
        worker,
        "make_embedder",
        lambda *_: (_ for _ in ()).throw(APIError(429, "ai_rate_limited", "limited")),
    )
    job = process(repo, bucket)
    assert job["status"] == "retry_wait" and job["stage"] == "embed"
    response = ask(repo, "alice", [kb["id"]], FakeAI(good_reply))
    assert response.status == "answered" and "document_processing" in response.source_limitations
    monkeypatch.setattr(evidence, "get_settings", lambda: SETTINGS)
    provision_id = response.citations[0].provision_version_id
    assert evidence.read(repo, user(repo, "alice"), provision_id)["id"] == provision_id
    with pytest.raises(APIError):
        ask(repo, "bob", [kb["id"]], FakeAI(good_reply))
    with pytest.raises(APIError):
        evidence.read(repo, user(repo, "bob"), provision_id)
    repo.rows[("knowledge_documents", doc["id"])]["deletedAt"] = date.today()
    with pytest.raises(APIError):
        evidence.read(repo, user(repo, "alice"), provision_id)


def test_empty_kb_can_use_opted_in_web_without_embedding(env, monkeypatch):
    repo, _ = env
    from app.services import web_sources

    item = web_sources.web_item(
        "https://vbpl.vn/test", "tối đa là 60 ngày", "60 ngày", "official_legal_text"
    )
    monkeypatch.setattr(web_sources, "gather", lambda *_: ([item], []))
    request = AskRequest(question="Thử việc bao lâu?", knowledge_base_ids=[], web_mode="official")
    answer = qa.answer(
        repo,
        user(repo, "alice"),
        request,
        FakeAI(good_reply),
        None,
        SETTINGS.model_copy(update={"official_web_enabled": True}),
    )
    assert answer.status == "answered" and answer.citations[0].source_url == "https://vbpl.vn/test"
    assert "web_validity_unverified" in answer.source_limitations


def test_web_workflow_broadens_query_and_answers_with_verified_source(env, monkeypatch):
    import httpx
    from app.services import web_sources

    repo, _ = env
    queries = []

    def handler(request):
        if request.method == "POST":
            queries.append(json.loads(request.content)["query"])
            rows = (
                []
                if len(queries) == 1
                else [
                    {
                        "type": "van_ban",
                        "data": {
                            "danh_sach_tep_van_ban": [
                                {
                                    "file_extension": "pdf",
                                    "duong_dan": "https://congbaocdn.chinhphu.vn/law.pdf",
                                }
                            ]
                        },
                    }
                ]
            )
            return httpx.Response(200, json={"success": True, "data": rows})
        return httpx.Response(
            200,
            text="<p>Điều 1. Quy định chung.</p><p>Điều 2. Thử việc tối đa là 60 ngày.</p><p>Điều 3. Quy định khác.</p>",
            headers={"content-type": "text/html"},
        )

    gather = web_sources.gather
    monkeypatch.setattr(
        web_sources,
        "gather",
        lambda ai, settings, query, mode, budget: gather(
            ai, settings, query, mode, budget, httpx.MockTransport(handler)
        ),
    )
    request = AskRequest(
        question="Thử việc gián đoạn thời hạn thế nào?", knowledge_base_ids=[], web_mode="official"
    )
    answer = qa.answer(
        repo,
        user(repo, "alice"),
        request,
        FakeAI(good_reply),
        None,
        SETTINGS.model_copy(update={"official_web_enabled": True}),
    )
    assert len(queries) == 2 and answer.status == "answered"
    assert answer.citations[0].source_url == "https://congbaocdn.chinhphu.vn/law.pdf"


def test_web_is_never_searched_without_opt_in(env, monkeypatch):
    repo, _ = env
    from app.services import web_sources

    def unexpected(*_):
        pytest.fail("web search must be opt-in")

    monkeypatch.setattr(web_sources, "gather", unexpected)
    request = AskRequest(question="Thử việc bao lâu?", knowledge_base_ids=[], web_mode="off")
    result = qa.answer(
        repo,
        user(repo, "alice"),
        request,
        FakeAI(good_reply),
        None,
        SETTINGS.model_copy(update={"official_web_enabled": True}),
    )
    assert result.status == "insufficient_evidence"


def test_embedding_failure_falls_back_to_exact_search(env, tmp_path):
    repo, bucket = env
    kb, _ = upload(repo, bucket, tmp_path)
    process(repo, bucket)

    class Limited:
        def embed(self, _):
            raise APIError(429, "ai_rate_limited", "limited")

    answer = qa.answer(
        repo,
        user(repo, "alice"),
        AskRequest(question="Điều 2 thử việc bao lâu?", knowledge_base_ids=[kb["id"]]),
        FakeAI(good_reply),
        Limited(),
        SETTINGS,
    )
    assert answer.status == "answered" and "embedding_unavailable" in answer.source_limitations


def test_embedding_limit_selects_middle_and_reports_coverage(env, tmp_path, monkeypatch):
    repo, bucket = env
    monkeypatch.setattr(
        parser,
        "extract_pages",
        lambda *_: ["\n".join(f"Điều {i}. Nội dung {i}" for i in range(1, 11))],
    )
    _, doc = upload(repo, bucket, tmp_path)
    limited = SETTINGS.model_copy(update={"embedding_max_chunks": 4})
    job = worker.run_once(repo, bucket, limited, "w1")
    assert job["status"] == "succeeded"
    assert knowledge.processing(repo, doc, limited)["embeddingCoverage"] == {
        "total": 10,
        "indexed": 4,
        "start": 4,
    }
    rows = repo.query(
        "search_chunks",
        [
            (
                "indexGeneration",
                "==",
                repo.get("knowledge_bases", doc["kbId"])["activeIndexGeneration"],
            )
        ],
    )
    assert sorted(int(row["searchText"].split("Điều ")[1].split()[0]) for row in rows) == [
        4,
        5,
        6,
        7,
    ]


def test_embedding_resumes_successful_batches_after_failure(env, tmp_path, monkeypatch):
    repo, bucket = env
    monkeypatch.setattr(
        parser,
        "extract_pages",
        lambda *_: ["\n".join(f"Điều {i}. Nội dung {i}" for i in range(1, 7))],
    )
    upload(repo, bucket, tmp_path)
    job = worker.claim(repo, SETTINGS, "w1")
    job["documentVersionId"] = pipeline.parse_stage(repo, bucket, SETTINGS, job)[
        "documentVersionId"
    ]
    settings = SETTINGS.model_copy(update={"embedding_batch_size": 2})

    class FailingEmbedder:
        def __init__(self):
            self.calls = 0

        def embed(self, texts):
            self.calls += 1
            if self.calls == 2:
                raise APIError(503, "ai_unavailable", "unavailable")
            return FakeEmbedder().embed(texts)

    with pytest.raises(APIError):
        pipeline.embed_stage(repo, settings, job, FailingEmbedder())
    assert len(repo.query("search_chunks")) == 2
    embedder = FailingEmbedder()
    embedder.calls = -10
    result = pipeline.embed_stage(repo, settings, job, embedder)
    assert embedder.calls == -8
    assert result["chunkCount"] == 6
    assert len(repo.query("search_chunks")) == 6


def test_failed_upload_is_not_reported_as_queued(env):
    repo, _ = env
    result = knowledge.processing(repo, {"fileState": "upload_failed"}, SETTINGS)
    assert result["status"] == "failed"
    assert result["stage"] == "upload"
    assert result["nextAction"] == "check_storage"
    assert result["retryable"] is False


def test_available_file_without_current_job_is_not_reported_as_queued(env):
    repo, _ = env
    doc = {"id": "d", "kbId": "k", "fileState": "available", "sha256": "hash"}
    result = knowledge.processing(repo, doc, SETTINGS)
    assert result["status"] == "failed"
    assert result["errorCode"] == "processing_job_missing"


def test_public_upload_can_build_and_search_openrouter_embedding_profile(env, tmp_path):
    repo, bucket = env
    settings = SETTINGS.model_copy(
        update={
            "embedding_provider": "openrouter",
            "openrouter_embedding_model": "nvidia/nemotron-3.5-embed-1b:free",
        }
    )
    kb = knowledge.create_kb(repo, user(repo, "alice"), "Kho", "t", settings)
    doc = knowledge.create_document(
        repo, user(repo, "alice"), kb["id"], {"displayTitle": "Luật mẫu"}, "t"
    )
    content = b"%PDF-1 synthetic public test"
    path = tmp_path / "public.pdf"
    path.write_bytes(content)
    options = knowledge.upload_options(
        user(repo, "alice"), kb["id"], doc["id"], "auto", settings, True
    )
    documents.upload_document(
        repo,
        bucket,
        doc["id"],
        str(path),
        len(content),
        hashlib.sha256(content).hexdigest(),
        "alice",
        "t",
        doc["version"],
        **options,
    )
    job = repo.query("processing_jobs")[0]
    assert job["publicEmbeddingInputConfirmed"] is True
    assert worker.run_once(repo, bucket, settings, "w-test")["status"] == "succeeded"
    request = AskRequest(
        question="Điều 2 thử việc bao lâu?",
        knowledge_base_ids=[kb["id"]],
        public_embedding_input_confirmed=True,
    )
    result = qa.answer(
        repo, user(repo, "alice"), request, FakeAI(good_reply), FakeEmbedder(), settings
    )
    assert result.status == "answered" and result.citations[0].provision_version_id


def test_switching_embedding_profile_never_mixes_existing_generation(env, tmp_path):
    repo, bucket = env
    kb, _ = upload(repo, bucket, tmp_path)
    assert process(repo, bucket)["status"] == "succeeded"
    previous = repo.get("knowledge_bases", kb["id"])["activeIndexGeneration"]
    new_settings = SETTINGS.model_copy(
        update={
            "embedding_provider": "openrouter",
            "openrouter_embedding_model": "nvidia/nemotron-3.5-embed-1b:free",
        }
    )
    doc = knowledge.create_document(
        repo, user(repo, "alice"), kb["id"], {"displayTitle": "Văn bản mới"}, "t"
    )
    path = tmp_path / "new.pdf"
    content = b"%PDF-1 another test"
    path.write_bytes(content)
    options = knowledge.upload_options(
        user(repo, "alice"), kb["id"], doc["id"], "auto", new_settings, True
    )
    documents.upload_document(
        repo,
        bucket,
        doc["id"],
        str(path),
        len(content),
        hashlib.sha256(content).hexdigest(),
        "alice",
        "t",
        doc["version"],
        **options,
    )
    result = worker.run_once(repo, bucket, new_settings, "w2")
    assert result["status"] == "failed" and result["errorCode"] == "embedding_profile_changed"
    assert repo.get("knowledge_bases", kb["id"])["activeIndexGeneration"] == previous
    request = AskRequest(question="Điều 2 thử việc bao lâu?", knowledge_base_ids=[kb["id"]])
    with pytest.raises(APIError) as error:
        qa.answer(
            repo, user(repo, "alice"), request, FakeAI(good_reply), FakeEmbedder(), new_settings
        )
    assert error.value.code == "embedding_profile_mismatch"


def test_answer_has_resolvable_citation_and_isolation(env, tmp_path):
    repo, bucket = env
    kb, _ = upload(repo, bucket, tmp_path)
    process(repo, bucket)
    response = ask(repo, "alice", [kb["id"]], FakeAI(good_reply))
    assert response.status == "answered"
    citation = response.citations[0]
    assert "[1]" in response.answer and citation.provision_version_id
    shown = evidence.read(repo, user(repo, "alice"), citation.provision_version_id)
    EvidenceOut.model_validate(shown)
    assert "60 ngày" in shown["text"] and "user_document_unverified" in shown["limitations"]
    with pytest.raises(APIError) as error:
        evidence.read(repo, user(repo, "bob"), citation.provision_version_id)
    assert error.value.status == 404
    with pytest.raises(APIError):
        ask(repo, "bob", [kb["id"]], FakeAI(good_reply))


def test_deleted_document_stops_serving_immediately(env, tmp_path):
    repo, bucket = env
    kb, doc = upload(repo, bucket, tmp_path)
    process(repo, bucket)
    ai = FakeAI(good_reply)
    provision = ask(repo, "alice", [kb["id"]], ai).citations[0].provision_version_id
    repo.rows[("knowledge_documents", doc["id"])].update(deletedAt=date.today())
    assert ask(repo, "alice", [kb["id"]], ai).status == "insufficient_evidence"
    with pytest.raises(APIError):
        evidence.read(repo, user(repo, "alice"), provision)


def test_delete_during_processing_is_cancelled_and_never_published(env, tmp_path):
    repo, bucket = env
    kb, doc = upload(repo, bucket, tmp_path)
    repo.rows[("knowledge_documents", doc["id"])].update(deletedAt=date.today())
    assert process(repo, bucket)["status"] == "cancelled"
    assert repo.get("knowledge_bases", kb["id"])["activeIndexGeneration"] is None


def test_expired_lease_is_recovered_and_stale_worker_is_fenced(env, tmp_path):
    repo, bucket = env
    upload(repo, bucket, tmp_path)
    stale = worker.claim(repo, SETTINGS, "dead")
    assert worker.claim(repo, SETTINGS, "other") is None
    key = ("processing_jobs", stale["id"])
    repo.rows[key]["nextRunAt"] = datetime(2000, 1, 1, tzinfo=timezone.utc)
    taken = worker.claim(repo, SETTINGS, "alive")
    assert taken["fence"] == stale["fence"] + 1
    with pytest.raises(worker.LostLease):
        worker.commit(repo, SETTINGS, stale, "dead", {"status": "succeeded"})


def test_temporary_error_retries_then_gives_up(env, monkeypatch, tmp_path):
    repo, bucket = env
    upload(repo, bucket, tmp_path)

    def boom(*_):
        raise TimeoutError()

    monkeypatch.setattr(worker, "make_embedder", boom)
    job = process(repo, bucket)
    assert job["status"] == "retry_wait" and job["stage"] == "embed" and job["failures"] == 1


def test_rate_limit_waits_without_exhausting_failure_budget(env, monkeypatch, tmp_path):
    repo, bucket = env
    _, doc = upload(repo, bucket, tmp_path)

    def limited(*_):
        raise APIError(429, "ai_rate_limited", "rate limited")

    monkeypatch.setattr(worker, "make_embedder", limited)
    job = process(repo, bucket)
    assert job["status"] == "retry_wait" and job["failures"] == 0
    assert job["rateLimitFailures"] == 1
    assert (job["nextRunAt"] - datetime.now(timezone.utc)).total_seconds() > 3500
    status = knowledge.processing(repo, doc, SETTINGS)
    assert status["nextAction"] == "wait_rate_limit" and status["nextRunAt"] == job["nextRunAt"]
    for _ in range(6):
        repo.rows[("processing_jobs", job["id"])]["nextRunAt"] = datetime(
            2000, 1, 1, tzinfo=timezone.utc
        )
        job = process(repo, bucket)
    assert job["status"] == "retry_wait" and job["failures"] == 0
    assert job["rateLimitFailures"] == 7


def test_quota_wait_reschedules_without_counting_as_failure(env, monkeypatch, tmp_path):
    from app.services.embeddings import EmbeddingQuotaWait

    repo, bucket = env
    upload(repo, bucket, tmp_path)
    retry_at = datetime(2030, 1, 1, tzinfo=timezone.utc)

    def quota(*_):
        raise EmbeddingQuotaWait(retry_at)

    monkeypatch.setattr(worker, "make_embedder", quota)
    job = process(repo, bucket)
    assert job["status"] == "retry_wait" and job["failures"] == 0
    assert job["nextRunAt"] == retry_at and job["errorCode"] == "embedding_quota_wait"


def test_missing_credentials_need_configuration_without_fallback(env, monkeypatch, tmp_path):
    repo, bucket = env
    upload(repo, bucket, tmp_path)

    def unavailable(*_):
        raise APIError(503, "ai_not_configured", "x")

    monkeypatch.setattr(worker, "make_embedder", unavailable)
    job = process(repo, bucket)
    assert job["status"] == "needs_configuration"
    doc = repo.query("knowledge_documents")[0]
    assert knowledge.processing(repo, doc, SETTINGS)["retryable"] is True


def test_scanned_pdf_reports_needs_ocr(env, monkeypatch, tmp_path):
    repo, bucket = env
    upload(repo, bucket, tmp_path)
    monkeypatch.setattr(parser, "extract_pages", lambda *_: ["", "", ""])
    job = process(repo, bucket)
    assert job["status"] == "needs_ocr"
    assert repo.query("search_chunks") == []


def test_shared_generation_needs_admin_publish(env, tmp_path):
    repo, bucket = env
    knowledge.ensure_shared_kb(repo, "t")
    content = b"%PDF-1 shared"
    digest = hashlib.sha256(content).hexdigest()
    path = "legal-documents/law1/a.pdf"
    bucket.store[path] = content
    repo.rows[("legal_documents", "law1")] = {
        "title": "Luật mẫu",
        "documentNumber": "01/2026/QH",
        "status": "effective",
        "effectiveDate": "2026-01-01",
        "fileState": "available",
        "deletedAt": None,
        "sha256": digest,
        "storagePath": path,
        "version": 1,
    }
    outbox = pipeline.job_outbox("shared", "legal_documents", "law1", "alice", "auto", SETTINGS)
    for name, row_id, row in outbox({"sha256": digest, "storagePath": path}):
        repo.put(name, row_id, row)
    assert process(repo, bucket)["status"] == "needs_review"
    kb = repo.get("knowledge_bases", "shared")
    assert kb["activeIndexGeneration"] is None
    assert ask(repo, "bob", None, FakeAI(good_reply)).status == "insufficient_evidence"
    generation, version = kb["latestGeneration"], kb["version"]
    knowledge.publish_generation(repo, "shared", generation, version, "alice", "t", SETTINGS)
    assert repo.query("processing_jobs")[0]["status"] == "succeeded"
    answer = ask(repo, "bob", None, FakeAI(good_reply))
    assert answer.status == "answered"
    assert "validity_unverified" not in answer.source_limitations


def test_hallucinated_or_unsupported_output_is_downgraded(env, tmp_path):
    repo, bucket = env
    kb, _ = upload(repo, bucket, tmp_path)
    process(repo, bucket)
    fake_id = json.dumps(
        {
            "status": "answered",
            "claims": [
                {"claim_id": "c1", "kind": "legal_rule", "text": "x", "evidence_ids": ["e99"]}
            ],
        }
    )
    ai = FakeAI(fake_id)
    response = ask(repo, "alice", [kb["id"]], ai)
    assert response.status == "insufficient_evidence" and ai.calls == 2
    assert response.citations == []


def test_exact_lookup_finds_article_without_vector(env, tmp_path):
    repo, bucket = env
    kb, _ = upload(repo, bucket, tmp_path)
    process(repo, bucket)
    request = AskRequest(
        question="Điều 2 khoản 1", knowledge_base_ids=[kb["id"]], retrieval_mode="keyword"
    )
    response = qa.answer(repo, user(repo, "alice"), request, FakeAI(good_reply), None, SETTINGS)
    assert response.status == "answered"
    plain = AskRequest(question="thử việc", knowledge_base_ids=[kb["id"]], retrieval_mode="keyword")
    result = qa.answer(repo, user(repo, "alice"), plain, FakeAI(good_reply), None, SETTINGS)
    assert result.status == "insufficient_evidence"
    assert "no_lexical_index" in result.source_limitations


def test_too_many_knowledge_bases_rejected(env, tmp_path):
    repo, _ = env
    with pytest.raises(APIError):
        qa.resolve_scope(repo, user(repo, "alice"), list("abcdef"), SETTINGS)


def test_routes_hide_other_users_private_knowledge_bases(env, monkeypatch):
    from app.core.security import verify_firebase_token
    from app.dependencies import get_bucket, get_repository
    from app.main import create_app
    from fastapi.testclient import TestClient

    repo, bucket = env
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_bucket] = lambda: bucket
    with TestClient(app, raise_server_exceptions=False) as client:
        app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "alice"}
        made = client.post("/api/v1/knowledge-bases", json={"title": "Riêng"})
        kb_id = made.json()["id"]
        doc = client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", json={"displayTitle": "A"})
        assert made.status_code == 201 and doc.status_code == 201
        pdf = {"content-type": "application/pdf", "if-match": '"1"'}
        url = f"/api/v1/knowledge-bases/{kb_id}/documents/{doc.json()['id']}"
        assert client.put(url + "/file", content=b"%PDF-1 x", headers=pdf).status_code == 200
        assert client.get(url + "/processing").json()["status"] == "queued"
        assert client.get(url + "/download").status_code == 200

        app.dependency_overrides[verify_firebase_token] = lambda: {"uid": "bob"}
        assert client.get("/api/v1/knowledge-bases").json() == []
        assert client.get(url + "/processing").status_code == 404
        assert client.get(url + "/download").status_code == 404
        assert client.delete(url, headers={"if-match": '"2"'}).status_code == 404
        assert client.get("/api/v1/evidence/anything").status_code == 404
        body = {"question": "Điều 1?", "knowledge_base_ids": [kb_id]}
        assert client.post("/api/v1/rag/ask", json=body).status_code in {404, 503}
        assert (
            client.post("/api/v1/admin/knowledge-bases/shared/publish", json={}).status_code == 403
        )


def test_reprocess_after_profile_change_preserves_pdf_and_queues_new_job(env, tmp_path):
    repo, bucket = env
    kb, doc = upload(repo, bucket, tmp_path)
    changed = SETTINGS.model_copy(update={"embedding_provider": "local"})
    before = knowledge.processing(repo, doc, changed)
    assert before["retryable"] and before["nextAction"] == "reindex"
    result = knowledge.reprocess(repo, doc, user(repo, "alice"), doc["version"], "t", changed)
    assert result["status"] == "queued"
    jobs = repo.query("processing_jobs")
    assert len(jobs) == 2
    local = next(j for j in jobs if j["embeddingProfileId"].startswith("local:"))
    assert local["sourceFence"]["storagePath"] == doc["storagePath"]
    assert local["sourceFence"]["sha256"] == doc["sha256"]
