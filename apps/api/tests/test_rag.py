from app.core.config import Settings
from app.schemas.rag import StoredChunk
from app.services.rag import answer_question, make_citations
from app.services.retrieval import retrieve_chunks


class FakeAI:
    def answer(self, question, chunks):
        return "Căn cứ Điều 1."


def test_insufficient_evidence_does_not_call_llm():
    result = answer_question("Hỏi", [], FakeAI(), Settings())
    assert result.has_sufficient_evidence is False
    assert result.citations == []


def test_citations_point_to_retrieved_chunks():
    chunk = StoredChunk(
        id="1",
        document_id="2",
        document_title="Luật mẫu",
        text="Nội dung",
        article="1",
        score=0.9,
    )
    citations = make_citations([chunk])
    assert citations[0].chunk_id == "1"
    assert citations[0].document_title == "Luật mẫu"


class FakeRow:
    id = "chunk-1"

    def to_dict(self):
        return {
            "document_id": "doc-1",
            "document_title": "Luật mẫu",
            "content": "Điều 1 quy định về hợp đồng.",
            "embedding": [1.0, 0.0],
            "article": "1",
        }


class FakeCollection:
    def limit(self, _limit):
        return self

    def stream(self):
        return [FakeRow()]


class FakeDatabase:
    def collection(self, _name):
        return FakeCollection()


def test_retrieval_reads_chunks_from_database():
    chunks = retrieve_chunks(FakeDatabase(), [1.0, 0.0], "hợp đồng", 5)
    assert chunks[0].id == "chunk-1"
    assert chunks[0].article == "1"
