import json

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import APIError
from app.evaluation.metrics import score
from app.ingestion.segmenter import segment
from app.ingestion.validation import NeedsOCR, check_pages, check_structure
from app.search.structured import parse_reference
from app.services import applicability, qa, web_sources

PACK = {
    "e1": {"sourceType": "official_legal_text", "text": "Thời gian thử việc tối đa là 60 ngày."},
    "e2": {"sourceType": "commentary", "text": "Bài viết bình luận."},
}


def output(**claim):
    base = {"claim_id": "c1", "kind": "legal_rule", "text": "x", "evidence_ids": ["e1"]}
    return json.dumps({"status": "answered", "claims": [{**base, **claim}]})


def test_valid_output_is_accepted_even_inside_code_fence():
    raw = "```json\n" + output(quote="tối đa là 60 ngày") + "\n```"
    assert qa.parse_output(raw, PACK, "").claims[0].claim_id == "c1"


@pytest.mark.parametrize(
    "claim",
    [
        {"evidence_ids": ["e9"]},  # invented evidence id
        {"evidence_ids": []},  # legal rule without any source
        {"evidence_ids": ["e2"]},  # commentary cannot back a legal rule
        {"quote": "một đoạn không có trong nguồn"},
        {"kind": "user_fact", "evidence_ids": [], "quote": "tôi làm 5 năm"},
        {"kind": "application_inference"},  # inference needs stated assumptions
    ],
)
def test_unsupported_claims_are_rejected(claim):
    with pytest.raises(ValueError):
        qa.parse_output(output(**claim), PACK, "tôi làm việc")


def test_user_fact_must_come_from_the_user():
    claim = {"kind": "user_fact", "evidence_ids": [], "quote": "tôi làm việc"}
    assert qa.parse_output(output(**claim), PACK, "Tôi làm việc 5 năm")


def test_clarification_needs_questions():
    with pytest.raises(ValueError):
        qa.parse_output('{"status": "needs_clarification"}', PACK, "")


def test_conflicting_versions_of_same_article_are_detected():
    base = {"number": "01/2026/QH", "identifier": "dieu-1", "provisionVersionId": "a"}
    one = {**base, "documentId": "d1", "text": "mức 10"}
    two = {**base, "documentId": "d2", "text": "mức 20", "provisionVersionId": "b"}
    assert qa.conflicts([one, two]) == [one, two]
    assert qa.conflicts([one, {**two, "number": "02/2026/QH"}]) == []


def test_reference_parsing():
    ref = parse_reference("Theo Điều 12 khoản 3 Luật 45/2019/QH14 thì sao?")
    assert ref == {"number": "45/2019/qh14", "article": "12", "clause": "3"}
    assert parse_reference("nghỉ phép năm") == {"number": None, "article": None, "clause": None}


def test_applicability_uses_legal_time_not_upload_time():
    from datetime import date

    past = {"validFrom": "2020-01-01", "endKind": "known_end", "validUntil": "2022-12-31"}
    assert applicability.check(past, date(2021, 6, 1))[0] is True
    assert applicability.check(past, date(2026, 1, 1))[0] is False
    assert applicability.check(past, date(2019, 1, 1))[0] is False
    assert "validity_unverified" in applicability.check({}, date(2026, 1, 1))[1]


def test_segmenter_keeps_article_clause_and_pages():
    pages = ["Chương I\nĐiều 1. A\nNội dung.\n2. Khoản hai", "Điều 2. B\n1. Một"]
    rows = segment(pages, 2000)
    assert [r["identifier"] for r in rows] == [
        "dieu-1",
        "dieu-1/khoan-2",
        "dieu-2",
        "dieu-2/khoan-1",
    ]
    assert rows[3]["pageStart"] == 2 and rows[0]["chapter"] == "I"
    assert check_structure(rows) == []


def test_long_provision_is_split_and_gaps_are_reported():
    rows = segment(["Điều 1. A\n" + "dòng dài\n" * 100, "Điều 3. C\nNội dung"], 200)
    assert sum(r["identifier"] == "dieu-1" for r in rows) > 1
    assert all(len(r["text"]) <= 200 for r in rows)
    assert "article_gap:1->3" in check_structure(rows)


def test_blank_pages_are_not_silently_published():
    with pytest.raises(NeedsOCR):
        check_pages(["", "", "Điều 1. Nội dung đủ dài để tính là có chữ"], False)
    assert (
        check_pages(["Điều 1. Nội dung đủ dài để tính là có chữ"] * 10, False)["blankPages"] == []
    )


def test_metrics_report_recall_status_and_leaks():
    cases = [
        {
            "id": "a",
            "required_evidence": ["p1"],
            "expected_status": "answered",
            "forbidden_evidence": ["x"],
        },
        {"id": "b", "required_evidence": ["p2"], "expected_status": "insufficient_evidence"},
    ]
    predictions = {
        "a": {
            "status": "answered",
            "citations": [{"provision_version_id": "p1"}],
            "retrieved_chunks": [{"id": "p1"}, {"id": "x"}],
        },
        "b": {"status": "answered", "citations": [], "retrieved_chunks": []},
    }
    result = score(cases, predictions)
    assert result["statusAccuracy"] == 0.5 and result["recallAtK"] == 0.5
    assert result["isolationLeaks"] == 1


def test_fetcher_blocks_private_addresses_and_plain_http(monkeypatch):
    monkeypatch.setattr(
        web_sources.socket, "getaddrinfo", lambda *_: [(2, 1, 6, "", ("169.254.169.254", 443))]
    )
    with pytest.raises(APIError):
        web_sources.fetch("https://vbpl.vn/x", Settings())
    with pytest.raises(APIError):
        web_sources.fetch("http://vbpl.vn/x", Settings())


def test_fetcher_revalidates_redirects_and_domain():
    def handler(request):
        if request.url.host == "vbpl.vn":
            return httpx.Response(302, headers={"location": "https://evil.example/x"})
        return httpx.Response(200, text="x", headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    with pytest.raises(APIError):
        web_sources.fetch("https://vbpl.vn/x", Settings(), ["vbpl.vn"], transport)


def test_fetcher_extracts_text_and_classifies_official_source():
    body = "<html><script>bad()</script><p>Điều 1. A</p><p>Điều 2. B</p><p>Điều 3. C</p></html>"
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, text=body, headers={"content-type": "text/html"})
    )
    url, text = web_sources.fetch("https://vbpl.vn/x", Settings(), ["vbpl.vn"], transport)
    assert "bad()" not in text and "Điều 3" in text
    assert web_sources.classify("vbpl.vn", text, Settings()) == "official_legal_text"
    assert web_sources.classify("blog.example", text, Settings()) == "commentary"
