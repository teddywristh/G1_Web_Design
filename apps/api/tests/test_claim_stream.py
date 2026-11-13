import json

import pytest

from app.services.claim_stream import ClaimStream

DOC = {
    "status": "answered",
    "assumptions": ["Người dùng nêu đủ dữ kiện"],
    "claims": [
        {"kind": "legal_rule", "text": 'Điều 1 "quy định" {mức} phạt', "evidence_ids": ["e1"]},
        {"kind": "example", "text": "Ví dụ [a]", "evidence_ids": ["e2"], "quote": "q\\n"},
    ],
    "missing_facts": [],
}


def feed_in_pieces(text, size):
    stream, found = ClaimStream(), []
    for start in range(0, len(text), size):
        found += stream.feed(text[start : start + size])
    return stream, found


@pytest.mark.parametrize("size", [1, 2, 3, 7, 50, 10_000])
def test_every_claim_is_found_whatever_the_chunking(size):
    text = json.dumps(DOC, ensure_ascii=False)
    _, found = feed_in_pieces(text, size)
    assert found == DOC["claims"]


def test_claims_arrive_as_soon_as_their_brace_closes():
    text = json.dumps(DOC, ensure_ascii=False)
    first_end = text.index('["e1"]}') + len('["e1"]}')
    stream = ClaimStream()
    assert stream.feed(text[: first_end - 1]) == []
    assert stream.feed(text[first_end - 1 : first_end]) == [DOC["claims"][0]]
    assert stream.feed(text[first_end:]) == [DOC["claims"][1]]


def test_code_fence_and_prose_around_the_json_are_ignored():
    text = "Đây là kết quả:\n```json\n" + json.dumps(DOC, ensure_ascii=False) + "\n```\nHết."
    _, found = feed_in_pieces(text, 5)
    assert found == DOC["claims"]


def test_status_and_assumptions_are_known_before_the_claims():
    stream = ClaimStream()
    stream.feed('{"status": "answered", "assumptions": ["a gi')
    assert stream.status == "answered" and stream.has_assumptions
    empty = ClaimStream()
    empty.feed('{"status": "needs_clarification", "assumptions": [], "claims": [')
    assert empty.status == "needs_clarification" and not empty.has_assumptions


def test_the_word_claims_inside_a_string_is_not_the_claims_array():
    text = json.dumps(
        {"status": "answered", "assumptions": ['"claims": [ {"x":1} ]'], "claims": [{"text": "a"}]}
    )
    _, found = feed_in_pieces(text, 3)
    assert found == [{"text": "a"}]


def test_a_second_array_after_claims_is_not_read_as_claims():
    text = json.dumps({"claims": [{"text": "a"}], "missing_facts": [{"text": "b"}]})
    _, found = feed_in_pieces(text, 4)
    assert found == [{"text": "a"}]


def test_incomplete_or_malformed_output_yields_nothing_extra():
    stream = ClaimStream()
    assert stream.feed('{"status": "answered", "claims": [{"text": "chưa xong') == []
    assert stream.feed("") == []
