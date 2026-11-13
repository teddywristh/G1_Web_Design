from datetime import date

from app.schemas.rag import AskRequest
from app.services import qa_cache

KBS = [{"id": "kb1", "generation": "g1"}]


def key(question="Tôi ăn trộm có bị phạt không?", kbs=KBS, as_of=date(2026, 1, 1), **fields):
    request = AskRequest(question=question, **fields)
    return qa_cache.key_for(kbs, request, as_of, "p1")


def test_case_accents_punctuation_and_spacing_do_not_change_the_key():
    assert key("Tôi ăn trộm có bị phạt không?") == key("  tôi  AN TRỘM có bị phạt không ")
    assert key("Điều 173 quy định gì?") == key("dieu 173 quy dinh gi")


def test_everything_that_shapes_the_answer_changes_the_key():
    base = key()
    assert key("Tôi ăn cắp có bị phạt không?") != base
    assert key(kbs=[{"id": "kb1", "generation": "g2"}]) != base  # a new corpus
    assert key(kbs=[{"id": "kb2", "generation": "g1"}]) != base
    assert key(as_of=date(2026, 1, 2)) != base
    assert key(model="other-model") != base
    assert key(web_mode="official") != base
    assert key(top_k=3) != base
    assert key(retrieval_mode="keyword") != base


def test_knowledge_base_order_does_not_matter():
    one = [{"id": "a", "generation": "1"}, {"id": "b", "generation": "2"}]
    assert key(kbs=one) == key(kbs=list(reversed(one)))


def test_entries_expire_and_least_recently_used_are_evicted():
    cache = qa_cache.AnswerCache()
    cache.put("a", {"v": 1}, limit=2)
    cache.put("b", {"v": 2}, limit=2)
    assert cache.get("a", ttl=60)["v"] == 1  # touching "a" makes "b" the oldest
    cache.put("c", {"v": 3}, limit=2)
    assert cache.get("b", ttl=60) is None and cache.get("a", ttl=60) and cache.get("c", ttl=60)
    cache.rows["a"]["at"] -= 100
    assert cache.get("a", ttl=60) is None
    assert "a" not in cache.rows
