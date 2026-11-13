"""QA workflow: free-form answer, follow-ups, router, web gating, cache, streaming, stage timing
and batched evidence reads."""

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
ANSWER = (
    "Thử việc tối đa 60 ngày [{key}].\n\n"
    "## Ví dụ\n"
    "- Hợp đồng 12 tháng: thử việc không quá 60 ngày [{key}]."
)


@pytest.fixture(autouse=True)
def fresh_cache():
    qa_cache.CACHE.clear()
    yield
    qa_cache.CACHE.clear()


def key_of(chunks):
    return next((c.text[1 : c.text.index("]")] for c in chunks if "60 ngày" in c.text), "e1")


def reply_with(template=ANSWER):
    """A model reply that cites whichever evidence id holds the 60-day rule."""
    return lambda chunks: template.format(key=key_of(chunks))


class RecordingAI:
    client = None

    def __init__(self, reply):
        self.reply, self.calls, self.options, self.prompts = reply, 0, [], []

    def text(self, chunks):
        return self.reply(chunks) if callable(self.reply) else self.reply

    def answer(self, question, chunks, **options):
        self.calls += 1
        self.options.append(options)
        self.prompts.append(question)
        return self.text(chunks)


class StreamingAI(RecordingAI):
    def __init__(self, reply, size=9):
        super().__init__(reply)
        self.size = size

    def answer_stream(self, question, chunks, **options):
        self.calls += 1
        self.options.append(options)
        self.prompts.append(question)
        text = self.text(chunks)
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


def ask_without_kb(repo, ai, question=QUESTION, settings=SETTINGS, **fields):
    request = AskRequest(question=question, knowledge_base_ids=[], **fields)
    return qa.answer(repo, user(repo, "alice"), request, ai, None, settings)


# --- the answer is the model's own ---------------------------------------------------------


def test_the_answer_is_what_the_model_wrote_with_numbered_citations(kb):
    repo, kb, _ = kb
    ai = RecordingAI(reply_with())
    result = ask(repo, kb, ai)
    assert ai.calls == 1 and result.status == "answered" and result.has_sufficient_evidence
    assert result.answer.startswith("Thử việc tối đa 60 ngày [1].")
    assert "## Ví dụ" in result.answer and "[e" not in result.answer
    assert len(result.citations) == 1 and result.citations[0].provision_version_id


def test_nothing_the_model_writes_is_dropped_or_sent_back(kb):
    repo, kb, _ = kb
    text = "Điều 999 quy định mức phạt 10 triệu [e9]. Thử việc tối đa 60 ngày [{key}]."
    ai = RecordingAI(reply_with(text))
    result = ask(repo, kb, ai)
    assert ai.calls == 1 and result.status == "answered"
    assert "Điều 999 quy định mức phạt 10 triệu" in result.answer
    assert "unsupported_claims_removed" not in result.source_limitations
    assert not any("validity" in note or "unverified" in note for note in result.source_limitations)


def test_a_source_the_model_did_not_cite_is_still_listed(kb):
    repo, kb, _ = kb
    result = ask(repo, kb, RecordingAI("Thử việc tối đa 60 ngày."))
    assert result.status == "answered" and result.citations


def test_the_prompt_asks_for_a_direct_answer_with_examples_not_for_questions_back(kb):
    repo, kb, _ = kb
    ai = RecordingAI(reply_with())
    ask(repo, kb, ai, question="Vi phạm gì thì bị xử lý hình sự nặng nhất?")
    prompt = ai.prompts[0]
    assert "Không hỏi lại" in prompt and "ví dụ tình huống" in prompt
    assert "[e1]" in prompt and "needs_clarification" not in prompt


def test_without_any_source_the_model_answers_from_its_own_knowledge(env):
    repo, _ = env
    ai = RecordingAI("Tội giết người có thể bị tử hình theo Điều 123 Bộ luật Hình sự.")
    result = ask_without_kb(repo, ai, question="Tội nào bị tử hình?")
    assert ai.calls == 1 and result.status == "answered"
    assert "Điều 123" in result.answer and result.citations == []
    assert "no_sources_general_knowledge" in result.source_limitations
    assert "Không có nguồn nào trong kho" in ai.prompts[0]


def test_an_empty_model_answer_is_reported_as_unavailable(kb):
    repo, kb, _ = kb
    result = ask(repo, kb, RecordingAI("   "))
    assert result.status == "temporarily_unavailable" and result.citations == []


# --- follow-up questions -------------------------------------------------------------------

EARLIER = [
    {"role": "user", "text": "Vi phạm gì thì bị xử lý hình sự nặng nhất?"},
    {"role": "assistant", "text": "Các tội có thể bị tử hình gồm giết người."},
]


def test_the_history_reaches_the_prompt_and_the_search(kb, monkeypatch):
    repo, kb, _ = kb
    looked_up = []
    real = qa.retrieve

    def spy(repo, kbs, request, *args):
        looked_up.append(request.question)
        return real(repo, kbs, request, *args)

    monkeypatch.setattr(qa, "retrieve", spy)
    ai = RecordingAI(reply_with())
    ask(repo, kb, ai, question="tất cả các loại luôn", history=EARLIER)
    assert "Hội thoại trước đó" in ai.prompts[0]
    assert "Các tội có thể bị tử hình gồm giết người." in ai.prompts[0]
    assert looked_up == ["Vi phạm gì thì bị xử lý hình sự nặng nhất? tất cả các loại luôn"]


def test_a_follow_up_is_never_served_from_the_cache(kb):
    repo, kb, _ = kb
    ai = RecordingAI(reply_with())
    for _ in range(2):
        ask(repo, kb, ai, history=EARLIER)
    assert ai.calls == 2 and not qa_cache.CACHE.rows


# --- router --------------------------------------------------------------------------------

ITEM = {"title": "Luật", "documentId": "d1", "via": "semantic"}


def plan_for(question="Tôi ăn trộm có bị phạt không", items=(ITEM,), settings=None, **fields):
    request = AskRequest(question=question, **fields)
    return qa.route(request, list(items), settings or Settings())


def test_a_short_plain_question_takes_the_fast_path():
    plan = plan_for()
    assert (plan.tier, plan.effort) == ("fast", "medium")


@pytest.mark.parametrize(
    "case",
    [
        {"question": "Tình huống dài. " * 30},
        {"question": "A là gì? B là gì? C là gì?"},
        {"question": "Hợp đồng có hiệu lực không", "session_facts": ["tôi làm 5 năm"]},
        {"question": "tất cả các loại luôn", "history": EARLIER},
        {"question": "Mức phạt hồi đó thế nào", "as_of": date(2020, 1, 1)},
        {"question": "So sánh thử việc và học việc"},
        {"question": "Hai bên khác nhau ở đâu"},
        {"question": "Hợp đồng nào", "items": [{**ITEM, "documentId": f"d{n}"} for n in range(4)]},
        {"question": "Hợp đồng nào", "items": [{**ITEM, "via": "web"}]},
    ],
)
def test_anything_complex_takes_the_deep_path(case):
    plan = plan_for(**case)
    assert (plan.tier, plan.effort) == ("deep", "medium")


def test_router_can_be_turned_off_and_then_sets_no_effort():
    plan = plan_for(settings=Settings(qa_router_enabled=False))
    assert plan.tier == "full" and plan.effort is None


def test_a_chosen_effort_beats_the_router_but_not_the_length_hint():
    assert plan_for(effort="high").effort == "high" and plan_for(effort="high").tier == "fast"
    assert plan_for("So sánh thử việc và học việc", effort="low").tier == "deep"
    assert plan_for(effort="low", settings=Settings(qa_router_enabled=False)).effort == "low"
    assert plan_for(effort="auto").effort == "medium"


def test_effort_is_part_of_the_cache_key(kb):
    repo, kb, _ = kb
    ai = RecordingAI(reply_with())
    ask(repo, kb, ai)
    assert ask(repo, kb, ai, effort="high").cache_hit is False
    assert ai.options[-1] == {"effort": "high"}


def test_effort_and_length_hint_reach_the_model(kb):
    repo, kb, _ = kb
    ai = RecordingAI(reply_with())
    ask(repo, kb, ai)
    assert ai.options == [{"effort": "medium"}] and qa.BUDGETS["fast"] in ai.prompts[0]
    ask(repo, kb, ai, question=QUESTION + " " + "Thêm tình huống. " * 30)
    assert qa.BUDGETS["deep"] in ai.prompts[-1]


# --- web only when needed ------------------------------------------------------------------


def web_settings(**fields):
    return SETTINGS.model_copy(update={"official_web_enabled": True, **fields})


def test_web_is_skipped_when_the_knowledge_base_already_has_evidence(kb, monkeypatch):
    repo, kb, _ = kb
    monkeypatch.setattr(web_sources, "gather", lambda *_: pytest.fail("web was not needed"))
    result = ask(repo, kb, RecordingAI(reply_with()), web_mode="official", settings=web_settings())
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
        RecordingAI(reply_with()),
        web_mode="official",
        settings=web_settings(qa_web_prefetch="always"),
    )
    assert seen == [QUESTION]


def test_web_runs_when_the_knowledge_base_found_nothing_and_is_cited(env, monkeypatch):
    repo, _ = env
    found = web_sources.web_item(
        "https://vbpl.vn/x", "Thời gian thử việc tối đa là 60 ngày", "q", "official_legal_text"
    )
    monkeypatch.setattr(web_sources, "gather", lambda *_: ([found], []))
    ai = RecordingAI("Thử việc tối đa 60 ngày [e1].")
    result = ask_without_kb(repo, ai, web_mode="official", settings=web_settings())
    assert result.status == "answered" and result.citations[0].source_url == "https://vbpl.vn/x"
    assert "no_sources_general_knowledge" not in result.source_limitations


# --- cache ---------------------------------------------------------------------------------


def test_a_repeated_question_is_served_from_the_cache_without_the_model(kb):
    repo, kb, _ = kb
    ai = RecordingAI(reply_with())
    first = ask(repo, kb, ai)
    assert first.cache_hit is False and ai.calls == 1
    again = ask(repo, kb, ai, question=QUESTION.upper().rstrip("?") + "  ")
    assert again.cache_hit is True and ai.calls == 1
    assert again.answer == first.answer and again.citations == first.citations
    assert again.run_id != first.run_id


def test_cache_is_not_used_for_other_dates_or_answers_with_user_facts(kb):
    repo, kb, _ = kb
    ai = RecordingAI(reply_with())
    ask(repo, kb, ai)
    assert ask(repo, kb, ai, as_of=date(2026, 6, 1)).cache_hit is False and ai.calls == 2
    ask(repo, kb, ai, session_facts=["tôi làm 5 năm"])
    ask(repo, kb, ai, session_facts=["tôi làm 5 năm"])
    assert ai.calls == 4


def test_cache_follows_the_published_generation(kb):
    repo, kb_row, _ = kb
    ai = RecordingAI(reply_with())
    ask(repo, kb_row, ai)
    repo.rows[("knowledge_bases", kb_row["id"])]["activeIndexGeneration"] = "newer-generation"
    assert ask(repo, kb_row, ai).cache_hit is False


def test_cached_answer_is_dropped_when_its_source_is_deleted(kb):
    repo, kb_row, doc = kb
    ai = RecordingAI(reply_with())
    ask(repo, kb_row, ai)
    assert ask(repo, kb_row, ai).cache_hit is True
    repo.rows[("knowledge_documents", doc["id"])]["deletedAt"] = date.today()
    ai.reply = "Thử việc tối đa 60 ngày theo Điều 25 Bộ luật Lao động."
    result = ask(repo, kb_row, ai)
    assert result.cache_hit is False and result.status == "answered"
    assert "no_sources_general_knowledge" in result.source_limitations
    assert ai.calls == 2  # the deleted source is gone, so the model answers without it


def test_cache_entries_expire(kb):
    repo, kb_row, _ = kb
    ai = RecordingAI(reply_with())
    ask(repo, kb_row, ai)
    for row in qa_cache.CACHE.rows.values():
        row["at"] -= SETTINGS.qa_cache_ttl_seconds + 1
    assert ask(repo, kb_row, ai).cache_hit is False and ai.calls == 2


def test_cache_can_be_disabled(kb):
    repo, kb_row, _ = kb
    ai = RecordingAI(reply_with())
    off = SETTINGS.model_copy(update={"qa_cache_enabled": False})
    ask(repo, kb_row, ai, settings=off)
    assert ask(repo, kb_row, ai, settings=off).cache_hit is False and ai.calls == 2


def test_answers_that_used_the_web_are_never_cached(env, monkeypatch):
    repo, _ = env
    found = web_sources.web_item(
        "https://vbpl.vn/x", "tối đa là 60 ngày", "q", "official_legal_text"
    )
    monkeypatch.setattr(web_sources, "gather", lambda *_: ([found], []))
    ai = RecordingAI("Thử việc tối đa 60 ngày [e1].")
    for _ in range(2):
        ask_without_kb(repo, ai, web_mode="official", settings=web_settings())
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
    events, kinds = run_events(repo, kb_row, RecordingAI(reply_with()), stream=False)
    assert kinds == ["stage", "sources", "stage", "done"]
    assert [e.get("stage") for e in events if e["type"] == "stage"] == ["retrieving", "drafting"]
    assert events[1]["items"][0]["title"] and events[1]["items"][0]["evidence_url"]
    assert events[-1]["response"].status == "answered"


@pytest.mark.parametrize("size", [1, 3, 7, 1000])
def test_the_answer_streams_as_it_is_written_and_matches_the_final_text(kb, size):
    repo, kb_row, _ = kb
    events, kinds = run_events(repo, kb_row, StreamingAI(reply_with(), size=size), stream=True)
    pieces = [e for e in events if e["type"] == "text"]
    assert kinds.index("text") < kinds.index("done")
    if size < 1000:
        assert len(pieces) > 3  # the answer arrives in parts, not in one block
    shown = "".join(e["text"] for e in pieces)
    final = events[-1]["response"]
    assert shown.strip() == final.answer  # a marker split across pieces is still numbered
    assert "[e" not in shown and "[1]" in shown
    cited = [c for e in pieces for c in e["citations"]]
    assert len(cited) == 1 and cited[0]["provision_version_id"]


def test_a_model_without_streaming_still_works_through_the_stream_path(kb):
    repo, kb_row, _ = kb
    ai = RecordingAI(reply_with())
    events, kinds = run_events(repo, kb_row, ai, stream=True)
    assert "text" not in kinds and events[-1]["response"].status == "answered"


def test_cache_hit_sends_one_cached_stage_and_the_response(kb):
    repo, kb_row, _ = kb
    ai = RecordingAI(reply_with())
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
    ask(repo, kb_row, RecordingAI(reply_with()))
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
    result = ask(repo, kb_row, RecordingAI(reply_with()))
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
