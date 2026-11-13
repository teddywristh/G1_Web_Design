"""Latency features of the QA workflow: router, claim-level validation, web gating, cache,
streaming, stage timing and batched evidence reads."""

import json
import logging
import time
from datetime import date

import pytest

from app.core.config import Settings
from app.schemas.rag import AskRequest
from app.services import evidence, qa, qa_cache, web_sources
from tests.memory_repo import MemoryRepo
from tests.test_knowledge_flow import (
    SETTINGS,
    FakeEmbedder,
    env,
    process,
    upload,
    user,
)

__all__ = ["env"]  # fixture imported from test_knowledge_flow

QUESTION = "Điều 2 thử việc bao lâu?"
RULE = {"kind": "legal_rule", "text": "Thử việc tối đa 60 ngày.", "quote": "tối đa là 60 ngày"}


@pytest.fixture(autouse=True)
def fresh_cache():
    qa_cache.CACHE.clear()
    yield
    qa_cache.CACHE.clear()


def key_of(chunks):
    return next(c.text[1 : c.text.index("]")] for c in chunks if "60 ngày" in c.text)


def reply_with(*claims, **fields):
    def build(chunks):
        key = key_of(chunks)
        body = {
            "status": "answered",
            "assumptions": [],
            "claims": [{**c, "evidence_ids": [key]} for c in claims],
            **fields,
        }
        return json.dumps(body, ensure_ascii=False)

    return build


class RecordingAI:
    client = None

    def __init__(self, reply):
        self.reply, self.calls, self.options = reply, 0, []

    def answer(self, question, chunks, **options):
        self.calls += 1
        self.options.append(options)
        return self.reply(chunks) if callable(self.reply) else self.reply


class StreamingAI(RecordingAI):
    def __init__(self, reply, size=9):
        super().__init__(reply)
        self.size = size

    def answer_stream(self, question, chunks, **options):
        self.calls += 1
        self.options.append(options)
        text = self.reply(chunks) if callable(self.reply) else self.reply
        for start in range(0, len(text), self.size):
            yield text[start : start + self.size]


@pytest.fixture
def kb(env, tmp_path):
    repo, bucket = env
    kb, doc = upload(repo, bucket, tmp_path)
    process(repo, bucket)
    return repo, kb, doc


def ask(repo, kb, ai, question=QUESTION, settings=SETTINGS, **fields):
    request = AskRequest(question=question, knowledge_base_ids=[kb["id"]], **fields)
    return qa.answer(repo, user(repo, "alice"), request, ai, FakeEmbedder(), settings)


# --- claim-level validation ----------------------------------------------------------------


def test_unsupported_claim_is_dropped_and_no_second_model_call_is_made(kb):
    repo, kb, _ = kb
    invented = {
        "kind": "legal_rule",
        "text": "Bịa.",
        "quote": "một đoạn hoàn toàn không có trong nguồn",
    }
    ai = RecordingAI(reply_with(RULE, invented))
    result = ask(repo, kb, ai)
    assert ai.calls == 1
    assert result.status == "answered"
    assert "Thử việc tối đa 60 ngày" in result.answer and "Bịa" not in result.answer
    assert "unsupported_claims_removed" in result.source_limitations
    assert [c.text for c in result.claim_citations] == ["Thử việc tối đa 60 ngày."]


def test_a_slightly_wrong_quote_is_repaired_not_retried(kb):
    repo, kb, _ = kb
    reworded = {**RULE, "quote": "thời gian thử việc tối đa 60 ngày"}  # the model dropped "là"
    ai = RecordingAI(reply_with(reworded))
    result = ask(repo, kb, ai)
    assert ai.calls == 1 and result.status == "answered"
    assert "unsupported_claims_removed" not in result.source_limitations


def test_output_with_nothing_supported_gets_exactly_one_retry(kb):
    repo, kb, _ = kb
    invented = {
        "kind": "legal_rule",
        "text": "Bịa.",
        "quote": "một đoạn hoàn toàn không có trong nguồn",
    }
    ai = RecordingAI(reply_with(invented))
    result = ask(repo, kb, ai)
    assert ai.calls == 2
    assert result.status == "insufficient_evidence"
    assert "output_validation_failed" in result.source_limitations


def test_a_retry_is_skipped_when_half_the_time_budget_is_gone(kb, monkeypatch):
    repo, kb, _ = kb
    ai = RecordingAI("không phải json")
    # The clock jumps past half of the 40s budget once the first model call has been made.
    monkeypatch.setattr(qa.time, "monotonic", lambda: 0.0 if ai.calls == 0 else 100.0)
    result = ask(repo, kb, ai)
    assert ai.calls == 1 and result.status == "insufficient_evidence"


def test_locate_quote_repairs_close_copies_and_rejects_inventions():
    item = {"text": "Điều 2. Thử việc\n1. Thời gian thử việc tối đa là 60 ngày đối với công việc."}
    found = qa.locate_quote("thời gian thử việc tối đa 60 ngày", [item])
    assert found and "tối đa là 60 ngày" in found
    assert qa.locate_quote("người lao động được nghỉ mười hai ngày", [item]) is None
    assert qa.locate_quote("ngắn", [item]) is None


def test_locate_quote_is_fast_on_long_sources():
    words = " ".join(f"từ{n}" for n in range(400))
    items = [{"text": words + " thời gian thử việc tối đa là 60 ngày " + words}] * 3
    started = time.perf_counter()
    qa.locate_quote("thời gian thử việc tối đa 60 ngày", items)
    assert time.perf_counter() - started < 1.5


# --- router --------------------------------------------------------------------------------

ITEM = {"title": "Luật", "documentId": "d1", "via": "semantic"}


def plan_for(question="Tôi ăn trộm có bị phạt không", items=(ITEM,), settings=None, **fields):
    request = AskRequest(question=question, **fields)
    return qa.route(request, list(items), settings or Settings())


def test_a_short_plain_question_takes_the_fast_path():
    plan = plan_for()
    assert (plan.tier, plan.effort, plan.max_claims) == ("fast", "low", 4)


@pytest.mark.parametrize(
    "case",
    [
        {"question": "Tình huống dài. " * 30},
        {"question": "A là gì? B là gì? C là gì?"},
        {"question": "Hợp đồng có hiệu lực không", "session_facts": ["tôi làm 5 năm"]},
        {"question": "Mức phạt hồi đó thế nào", "as_of": date(2020, 1, 1)},
        {"question": "So sánh thử việc và học việc"},
        {"question": "Hai bên khác nhau ở đâu"},
        {"question": "Hợp đồng nào", "items": [{**ITEM, "documentId": f"d{n}"} for n in range(4)]},
        {"question": "Hợp đồng nào", "items": [{**ITEM, "via": "web"}]},
    ],
)
def test_anything_complex_takes_the_deep_path(case):
    plan = plan_for(**case)
    assert (plan.tier, plan.effort, plan.max_claims) == ("deep", "medium", 8)


def test_router_can_be_turned_off_and_then_sets_no_effort():
    plan = plan_for(settings=Settings(qa_router_enabled=False))
    assert plan.tier == "full" and plan.effort is None


def test_effort_reaches_the_model_and_the_prompt_asks_for_a_short_answer(kb):
    repo, kb, _ = kb
    prompts = []

    class Spy(RecordingAI):
        def answer(self, question, chunks, **options):
            prompts.append(question)
            return super().answer(question, chunks, **options)

    ai = Spy(reply_with(RULE))
    ask(repo, kb, ai)
    assert ai.options == [{"effort": "low"}]
    assert "tối đa 4 claims" in prompts[0]
    ai = Spy(reply_with(RULE))
    ask(repo, kb, ai, question=QUESTION + " " + "Thêm tình huống. " * 30)
    assert ai.options == [{"effort": "medium"}] and "Tối đa 8 claims" in prompts[-1]


# --- web only when needed ------------------------------------------------------------------


def web_settings(**fields):
    return SETTINGS.model_copy(update={"official_web_enabled": True, **fields})


def test_web_is_skipped_when_the_knowledge_base_already_has_evidence(kb, monkeypatch):
    repo, kb, _ = kb
    monkeypatch.setattr(web_sources, "gather", lambda *_: pytest.fail("web was not needed"))
    result = ask(
        repo, kb, RecordingAI(reply_with(RULE)), web_mode="official", settings=web_settings()
    )
    assert result.status == "answered"


def test_web_can_still_run_first_when_configured_to(kb, monkeypatch):
    repo, kb, _ = kb
    seen = []

    def gather(ai, settings, query, mode, budget):
        seen.append(query)
        return [], []

    monkeypatch.setattr(web_sources, "gather", gather)
    ask(
        repo,
        kb,
        RecordingAI(reply_with(RULE)),
        web_mode="official",
        settings=web_settings(qa_web_prefetch="always"),
    )
    assert seen == [QUESTION]


def test_web_runs_as_a_follow_up_when_the_model_reports_missing_evidence(kb, monkeypatch):
    repo, kb, _ = kb
    found = web_sources.web_item(
        "https://vbpl.vn/x", "Nguồn mới: tối đa là 60 ngày", "q", "official_legal_text"
    )
    searches = []

    def gather(ai, settings, query, mode, budget):
        searches.append(query)
        budget["searches"] += 1
        return [found], []

    monkeypatch.setattr(web_sources, "gather", gather)

    def reply(chunks):
        if len(chunks) and not any("vbpl.vn" in c.text or "Nguồn mới" in c.text for c in chunks):
            return json.dumps({"status": "insufficient_evidence", "search_queries": ["thử việc"]})
        key = next(c.text[1 : c.text.index("]")] for c in chunks if "Nguồn mới" in c.text)
        return json.dumps(
            {
                "status": "answered",
                "claims": [{**RULE, "quote": "tối đa là 60 ngày", "evidence_ids": [key]}],
            }
        )

    ai = RecordingAI(reply)
    result = ask(repo, kb, ai, web_mode="official", settings=web_settings())
    assert searches == ["thử việc"] and ai.calls == 2
    assert result.status == "answered"
    assert result.citations[0].source_url == "https://vbpl.vn/x"


# --- cache ---------------------------------------------------------------------------------


def test_a_repeated_question_is_served_from_the_cache_without_the_model(kb):
    repo, kb, _ = kb
    ai = RecordingAI(reply_with(RULE))
    first = ask(repo, kb, ai)
    assert first.cache_hit is False and ai.calls == 1
    again = ask(repo, kb, ai, question=QUESTION.upper().rstrip("?") + "  ")
    assert again.cache_hit is True and ai.calls == 1
    assert again.answer == first.answer and again.citations == first.citations
    assert again.run_id != first.run_id


def test_cache_is_not_used_for_other_dates_or_answers_with_user_facts(kb):
    repo, kb, _ = kb
    ai = RecordingAI(reply_with(RULE))
    ask(repo, kb, ai)
    assert ask(repo, kb, ai, as_of=date(2026, 6, 1)).cache_hit is False and ai.calls == 2
    ask(repo, kb, ai, session_facts=["tôi làm 5 năm"])
    ask(repo, kb, ai, session_facts=["tôi làm 5 năm"])
    assert ai.calls == 4


def test_cache_follows_the_published_generation(kb):
    repo, kb_row, _ = kb
    ai = RecordingAI(reply_with(RULE))
    ask(repo, kb_row, ai)
    repo.rows[("knowledge_bases", kb_row["id"])]["activeIndexGeneration"] = "newer-generation"
    assert ask(repo, kb_row, ai).cache_hit is False


def test_cached_answer_is_dropped_when_its_source_is_deleted(kb):
    repo, kb_row, doc = kb
    ai = RecordingAI(reply_with(RULE))
    ask(repo, kb_row, ai)
    assert ask(repo, kb_row, ai).cache_hit is True
    repo.rows[("knowledge_documents", doc["id"])]["deletedAt"] = date.today()
    result = ask(repo, kb_row, ai)
    assert result.cache_hit is False and result.status == "insufficient_evidence"
    assert ai.calls == 1  # the deleted source leaves nothing to ask the model about


def test_cache_entries_expire(kb):
    repo, kb_row, _ = kb
    ai = RecordingAI(reply_with(RULE))
    ask(repo, kb_row, ai)
    for row in qa_cache.CACHE.rows.values():
        row["at"] -= SETTINGS.qa_cache_ttl_seconds + 1
    assert ask(repo, kb_row, ai).cache_hit is False and ai.calls == 2


def test_cache_can_be_disabled(kb):
    repo, kb_row, _ = kb
    ai = RecordingAI(reply_with(RULE))
    off = SETTINGS.model_copy(update={"qa_cache_enabled": False})
    ask(repo, kb_row, ai, settings=off)
    assert ask(repo, kb_row, ai, settings=off).cache_hit is False and ai.calls == 2


def test_answers_that_used_the_web_are_never_cached(env, monkeypatch):
    repo, _ = env
    found = web_sources.web_item(
        "https://vbpl.vn/x", "tối đa là 60 ngày", "q", "official_legal_text"
    )
    monkeypatch.setattr(web_sources, "gather", lambda *_: ([found], []))
    reply = lambda chunks: json.dumps(  # noqa: E731
        {
            "status": "answered",
            "claims": [{**RULE, "evidence_ids": ["e1"]}],
        }
    )
    ai = RecordingAI(reply)
    request = AskRequest(question="Thử việc bao lâu?", knowledge_base_ids=[], web_mode="official")
    for _ in range(2):
        qa.answer(repo, user(repo, "alice"), request, ai, None, web_settings())
    assert ai.calls == 2 and not qa_cache.CACHE.rows


# --- events, streaming, timing -------------------------------------------------------------


def run_events(repo, kb, ai, stream, **fields):
    request = AskRequest(question=QUESTION, knowledge_base_ids=[kb["id"]], **fields)
    events = list(
        qa.answer_events(
            repo, user(repo, "alice"), request, ai, FakeEmbedder(), SETTINGS, stream=stream
        )
    )
    return events, [e["type"] for e in events]


def test_events_report_stages_sources_and_the_final_response(kb):
    repo, kb_row, _ = kb
    events, kinds = run_events(repo, kb_row, RecordingAI(reply_with(RULE)), stream=False)
    assert kinds == ["stage", "sources", "stage", "done"]
    assert [e.get("stage") for e in events if e["type"] == "stage"] == ["retrieving", "drafting"]
    assert events[1]["items"][0]["title"] and events[1]["items"][0]["evidence_url"]
    assert events[-1]["response"].status == "answered"


def test_claims_stream_one_by_one_and_match_the_final_answer(kb):
    repo, kb_row, _ = kb
    second = {"kind": "example", "text": "Ví dụ thử việc.", "quote": "tối đa là 60 ngày"}
    ai = StreamingAI(reply_with(RULE, second), size=7)
    events, kinds = run_events(repo, kb_row, ai, stream=True)
    claims = [e for e in events if e["type"] == "claim"]
    assert kinds.index("claim") < kinds.index("done")
    assert [c["text"] for c in claims] == ["Thử việc tối đa 60 ngày. [1]", "Ví dụ thử việc. [1]"]
    assert len(claims[0]["citations"]) == 1 and claims[1]["citations"] == []
    assert claims[0]["citations"][0]["provision_version_id"]
    final = events[-1]["response"]
    assert final.answer == "\n".join(c["text"] for c in claims)


def test_unsupported_claims_are_never_streamed(kb):
    repo, kb_row, _ = kb
    invented = {
        "kind": "legal_rule",
        "text": "Bịa.",
        "quote": "một đoạn hoàn toàn không có trong nguồn",
    }
    events, _ = run_events(repo, kb_row, StreamingAI(reply_with(invented, RULE)), stream=True)
    assert [e["text"] for e in events if e["type"] == "claim"] == ["Thử việc tối đa 60 ngày. [1]"]


def test_an_inference_is_streamed_only_after_its_assumptions(kb):
    repo, kb_row, _ = kb
    inference = {
        "kind": "application_inference",
        "text": "Áp dụng cho bạn.",
        "quote": "tối đa là 60 ngày",
    }
    with_assumption = reply_with(inference, assumptions=["Bạn đang thử việc"])
    without = lambda chunks: json.dumps(  # noqa: E731
        {
            "status": "answered",
            "claims": [
                {**inference, "evidence_ids": [key_of(chunks)]},
                {**RULE, "evidence_ids": [key_of(chunks)]},
            ],
        }
    )
    shown, _ = run_events(repo, kb_row, StreamingAI(with_assumption), stream=True)
    assert [e["text"] for e in shown if e["type"] == "claim"] == ["Áp dụng cho bạn. [1]"]
    qa_cache.CACHE.clear()
    shown, _ = run_events(repo, kb_row, StreamingAI(without), stream=True)
    assert [e["text"] for e in shown if e["type"] == "claim"] == ["Thử việc tối đa 60 ngày. [1]"]
    assert shown[-1]["response"].answer.count("\n") == 0  # the unsupported inference is also gone


def test_clarifications_stream_no_claims(kb):
    repo, kb_row, _ = kb
    reply = json.dumps({"status": "needs_clarification", "missing_facts": ["Bạn làm bao lâu?"]})
    events, kinds = run_events(repo, kb_row, StreamingAI(reply), stream=True)
    assert "claim" not in kinds
    assert events[-1]["response"].status == "needs_clarification"


def test_a_bad_first_output_resets_what_was_shown_and_retries(kb):
    repo, kb_row, _ = kb
    outputs = iter(["không phải json", None])

    def reply(chunks):
        first = next(outputs)
        return first if first else reply_with(RULE)(chunks)

    events, kinds = run_events(repo, kb_row, StreamingAI(reply), stream=True)
    assert "reset" in kinds and kinds.index("reset") < kinds.index("claim")
    assert events[-1]["response"].status == "answered"


def test_a_model_without_streaming_still_works_through_the_stream_path(kb):
    repo, kb_row, _ = kb
    ai = RecordingAI(reply_with(RULE))
    events, kinds = run_events(repo, kb_row, ai, stream=True)
    assert "claim" not in kinds and events[-1]["response"].status == "answered"


def test_cache_hit_sends_one_cached_stage_and_the_response(kb):
    repo, kb_row, _ = kb
    ai = RecordingAI(reply_with(RULE))
    ask(repo, kb_row, ai)
    events, kinds = run_events(repo, kb_row, ai, stream=True)
    assert kinds == ["stage", "done"] and events[0]["stage"] == "cached"
    assert events[1]["response"].cache_hit is True


@pytest.fixture
def api_log():
    """The app logger does not propagate to the root logger, so listen on it directly."""
    lines = []

    class Collect(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())

    logger = logging.getLogger("legal_api")
    handler, level = Collect(), logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield lines
    logger.removeHandler(handler)
    logger.setLevel(level)


def test_each_question_logs_where_the_time_went(kb, api_log):
    repo, kb_row, _ = kb
    ask(repo, kb_row, RecordingAI(reply_with(RULE)))
    lines = [json.loads(m) for m in api_log if '"qa_timing"' in m]
    assert len(lines) == 1
    line = lines[0]
    assert line["status"] == "answered" and line["tier"] == "fast" and line["cache"] == "miss"
    assert line["llmCalls"] == 1 and line["evidenceItems"] >= 1
    assert {"scope", "cache", "embed", "search", "validate", "expand", "llm"} <= set(
        line["stagesMs"]
    )
    assert QUESTION not in json.dumps(line)  # timing lines carry no question text


def test_audit_row_is_written_in_the_background_with_latency(kb):
    repo, kb_row, _ = kb
    result = ask(repo, kb_row, RecordingAI(reply_with(RULE)))
    qa.RUN_LOG.submit(lambda: None).result(timeout=5)  # the writer pool is FIFO per worker
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not repo.get("evidence_runs", result.run_id):
        time.sleep(0.02)
    row = repo.get("evidence_runs", result.run_id)
    assert row["tier"] == "fast" and row["cacheHit"] is False and row["latencyMs"] >= 0
    assert row["policyVersion"] == qa.POLICY_VERSION


# --- batched evidence reads ----------------------------------------------------------------


class CountingRepo(MemoryRepo):
    def __init__(self):
        super().__init__()
        self.gets = self.batches = self.queries = 0
        self.single = []

    def get(self, collection, doc_id):
        self.gets += 1
        self.single.append((collection, doc_id))
        return super().get(collection, doc_id)

    def get_many(self, collection, doc_ids):
        self.batches += 1
        rows = {i: MemoryRepo.get(self, collection, i) for i in dict.fromkeys(doc_ids) if i}
        return {i: row for i, row in rows.items() if row is not None}

    def query(self, *args, **kwargs):
        # MemoryRepo.query builds its rows with self.get; those are not extra round trips.
        self.queries += 1
        before = len(self.single)
        rows = super().query(*args, **kwargs)
        self.gets -= len(self.single) - before
        del self.single[before:]
        return rows


def test_validating_many_candidates_uses_batched_reads(kb):
    repo, kb_row, _ = kb
    counting = CountingRepo()
    counting.rows = repo.rows
    generation = repo.rows[("knowledge_bases", kb_row["id"])]["activeIndexGeneration"]
    candidates = [
        {"provisionVersionId": row["id"], "generation": generation}
        for row in repo.query("provision_versions")
    ]
    assert len(candidates) >= 3
    items = evidence.build(counting, candidates, {kb_row["id"]}, date.today(), 20, SETTINGS)
    assert len(items) == len(candidates)
    assert counting.gets == 0 and counting.batches == 3  # provisions, sources, search chunks


def test_expansion_queries_each_article_once_and_batches_the_rest(kb):
    repo, kb_row, _ = kb
    counting = CountingRepo()
    counting.rows = repo.rows
    generation = repo.rows[("knowledge_bases", kb_row["id"])]["activeIndexGeneration"]
    rows = [r for r in repo.query("provision_versions") if r["articleNo"] == "2"]
    assert len(rows) >= 2  # one article, several clauses
    candidates = [{"provisionVersionId": r["id"], "generation": generation} for r in rows[:1]]
    items = evidence.build(counting, candidates, {kb_row["id"]}, date.today(), 20, SETTINGS)
    counting.gets = counting.batches = counting.queries = 0
    both = items + evidence.build(
        counting,
        [{"provisionVersionId": rows[1]["id"], "generation": generation}],
        {kb_row["id"]},
        date.today(),
        20,
        SETTINGS,
    )
    counting.gets = counting.batches = counting.queries = 0
    expanded = evidence.expand(counting, both, {kb_row["id"]}, date.today(), 12, SETTINGS)
    assert counting.queries == 1  # two clauses of one article share a single sibling query
    assert counting.gets == 0, counting.single
    assert len(expanded) >= len(both)


def test_read_cache_falls_back_to_plain_gets_without_a_batch_api():
    class Plain:
        def __init__(self):
            self.calls = 0

        def get(self, collection, doc_id):
            self.calls += 1
            return {"id": doc_id}

    plain = Plain()
    reads = evidence.ReadCache(plain)
    reads.prefetch("c", ["a", "b"])
    assert plain.calls == 0  # nothing to batch with; reads happen on demand
    assert reads.get("c", "a") == {"id": "a"} and reads.get("c", "a") == {"id": "a"}
    assert plain.calls == 1
