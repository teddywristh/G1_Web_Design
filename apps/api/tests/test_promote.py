"""An administrator moves an indexed private document to the shared library without embedding."""

import pytest

from app.core.errors import APIError
from app.services import knowledge
from tests.test_knowledge_flow import (
    SETTINGS,
    FakeAI,
    env,
    good_reply,
    process,
    upload,
    user,
)
from tests.test_knowledge_flow import ask as ask_question

__all__ = ["env"]

META = {
    "title": "Bộ luật mẫu",
    "documentNumber": "01/2026/QH",
    "documentType": "Bộ luật",
    "issuingAuthority": "Quốc hội",
    "issueDate": "2026-01-01",
    "effectiveDate": "2026-01-01",
    "status": "effective",
    "sourceUrl": None,
}


@pytest.fixture
def indexed(env, tmp_path, monkeypatch):
    repo, bucket = env
    kb, doc = upload(repo, bucket, tmp_path)
    process(repo, bucket)
    embedded = []
    from app.workers import ingestion as worker

    class Counting:
        def embed(self, texts):
            embedded.extend(texts)
            return [[1.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr(worker, "make_embedder", lambda *_: Counting())
    return repo, bucket, kb, doc, embedded


def test_a_private_document_reaches_everyone_without_being_embedded_again(indexed):
    repo, bucket, kb, doc, embedded = indexed
    promoted = knowledge.promote_document(
        repo, user(repo, "alice"), kb["id"], doc["id"], META, SETTINGS, "t"
    )
    assert promoted["fileState"] == "pending_upload"  # not usable before the worker has copied it
    job = process(repo, bucket)
    assert job["status"] == "needs_review" and job["stage"] == "publish"
    assert embedded == []  # the vectors were copied, not recomputed

    shared = repo.get("knowledge_bases", knowledge.SHARED)
    assert shared["latestGeneration"] and not shared["activeIndexGeneration"]
    assert ask_question(repo, "bob", None, FakeAI(good_reply)).citations == []  # not live yet

    knowledge.publish_generation(
        repo,
        knowledge.SHARED,
        shared["latestGeneration"],
        shared["version"],
        "alice",
        "t",
        SETTINGS,
    )
    answer = ask_question(repo, "bob", None, FakeAI(good_reply))  # bob owns no knowledge base
    assert answer.status == "answered" and answer.citations
    citation = answer.citations[0]
    assert citation.source_type == "official_legal_text"
    assert citation.document_title == "Bộ luật mẫu"
    assert repo.get("legal_documents", promoted["id"])["fileState"] == "available"
    assert repo.get("knowledge_documents", doc["id"])["promotedTo"] == promoted["id"]


def test_the_shared_copy_has_its_own_file_and_rows_and_the_private_one_is_untouched(indexed):
    repo, bucket, kb, doc, _ = indexed
    promoted = knowledge.promote_document(
        repo, user(repo, "alice"), kb["id"], doc["id"], META, SETTINGS, "t"
    )
    process(repo, bucket)
    shared_doc = repo.get("legal_documents", promoted["id"])
    assert shared_doc["storagePath"] != doc["storagePath"]
    assert bucket.store[shared_doc["storagePath"]] == bucket.store[doc["storagePath"]]
    own = repo.query("provision_versions", [("sourceId", "==", doc["id"])], limit=100)
    copied = repo.query("provision_versions", [("sourceId", "==", promoted["id"])], limit=100)
    assert own and len(copied) == len(own)
    assert {row["kbId"] for row in copied} == {knowledge.SHARED}
    assert {row["validityReviewState"] for row in copied} == {"reviewed"}
    assert all(row["kbId"] == kb["id"] for row in own)


def test_a_document_that_is_not_indexed_or_already_moved_is_refused(env, tmp_path, indexed):
    repo, bucket, kb, doc, _ = indexed
    alice = user(repo, "alice")
    knowledge.promote_document(repo, alice, kb["id"], doc["id"], META, SETTINGS, "t")
    with pytest.raises(APIError) as twice:
        knowledge.promote_document(repo, alice, kb["id"], doc["id"], META, SETTINGS, "t")
    assert twice.value.code == "already_shared"
    other_kb, other = upload(repo, bucket, tmp_path, content=b"%PDF-1 other")  # not processed yet
    with pytest.raises(APIError) as waiting:
        knowledge.promote_document(repo, alice, other_kb["id"], other["id"], META, SETTINGS, "t")
    assert waiting.value.code == "not_indexed"


def test_nobody_can_move_someone_elses_document(indexed):
    repo, _, kb, doc, _ = indexed
    with pytest.raises(APIError) as error:
        knowledge.promote_document(
            repo, user(repo, "bob"), kb["id"], doc["id"], META, SETTINGS, "t"
        )
    assert error.value.status == 404
