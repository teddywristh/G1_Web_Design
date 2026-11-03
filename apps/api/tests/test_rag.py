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


def test_public_vbpl_search_and_fetch_need_no_api_key():
    from types import SimpleNamespace

    def handler(request):
        if "vbpq-timkiem" in request.url.path:
            assert "Keyword" in request.url.params
            return httpx.Response(
                200,
                text='<a href="/TW/Pages/vbpq-toanvan.aspx?ItemID=123">Luật</a><a href="https://evil.example/vbpq-toanvan.aspx?ItemID=1">bad</a>',
                headers={"content-type": "text/html"},
            )
        return httpx.Response(
            200,
            text="<p>Điều 1. Một</p><p>Điều 2. Hai</p><p>Điều 3. Ba</p>",
            headers={"content-type": "text/html"},
        )

    settings = Settings(official_web_enabled=True)
    items, notes = web_sources.gather(
        SimpleNamespace(client=None),
        settings,
        "Điều 2 quy định gì",
        "official",
        {"searches": 0, "fetches": 0},
        httpx.MockTransport(handler),
    )
    assert not notes
    assert (
        len(items) == 1
        and items[0]["sourceUrl"] == "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123"
    )
    assert items[0]["sourceType"] == "official_legal_text"


def test_congbao_search_uses_public_api_and_official_pdfs_only():
    def handler(request):
        assert request.url.host == "api-searchcongbao.chinhphu.vn"
        assert json.loads(request.content)["query"] == "giết người"
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": [
                    {
                        "type": "van_ban",
                        "data": {
                            "loai_van_ban": "Văn bản hợp nhất",
                            "ngay_ban_hanh": "2025-09-05",
                            "danh_sach_tep_van_ban": [
                                {
                                    "file_extension": "pdf",
                                    "duong_dan": "https://congbaocdn.chinhphu.vn/doc.pdf",
                                },
                                {
                                    "file_extension": "pdf",
                                    "duong_dan": "https://evil.example/doc.pdf",
                                },
                            ],
                        },
                    }
                ],
            },
        )

    urls = web_sources.congbao_search_urls(
        "Giết người có bị đi tù không", Settings(), httpx.MockTransport(handler)
    )
    assert urls == ["https://congbaocdn.chinhphu.vn/doc.pdf"]


def test_congbao_prioritizes_relevance_and_omits_conversational_words():
    def handler(request):
        assert json.loads(request.content)["query"] == "tội cố ý giết người"

        def document(score, kind, filename):
            return {
                "type": "van_ban",
                "data": {
                    "score": score,
                    "loai_van_ban": kind,
                    "danh_sach_tep_van_ban": [
                        {
                            "file_extension": "pdf",
                            "duong_dan": f"https://congbaocdn.chinhphu.vn/{filename}.pdf",
                        }
                    ],
                },
            }

        return httpx.Response(
            200,
            json={
                "success": True,
                "data": [
                    document(0.1, "Văn bản hợp nhất", "unrelated"),
                    document(0.9, "Quyết định", "relevant"),
                ],
            },
        )

    urls = web_sources.congbao_search_urls(
        "Bạn xem tội cố ý giết người nhưng nạn nhân chưa thiệt mạng thì có bị tử hình không",
        Settings(),
        httpx.MockTransport(handler),
    )
    assert urls[0].endswith("/relevant.pdf")


def test_congbao_search_retries_shorter_query_when_no_documents():
    queries = []

    def handler(request):
        query = json.loads(request.content)["query"]
        queries.append(query)
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
                                "duong_dan": "https://congbaocdn.chinhphu.vn/labor.pdf",
                            }
                        ]
                    },
                }
            ]
        )
        return httpx.Response(200, json={"success": True, "data": rows})

    urls = web_sources.congbao_search_urls(
        "Hợp đồng lao động có cần ký hợp đồng bằng văn bản không?",
        Settings(),
        httpx.MockTransport(handler),
    )
    assert len(queries) == 2 and queries[1] == "hợp đồng"
    assert urls == ["https://congbaocdn.chinhphu.vn/labor.pdf"]


def test_relevant_legal_section_keeps_following_penalty():
    text = "Điều 122. Khác\nNgười phạm tội khác.\nĐiều 123. Tội giết người\nPhạt tù từ 12 năm.\nĐiều 124. Khác\nNội dung khác."
    window = web_sources.best_window(text, "Giết người có bị đi tù không")
    assert "Điều 123" in window and "Phạt tù" in window and "Điều 124" not in window


def test_relevant_section_prioritizes_topic_over_question_modifiers():
    text = (
        "Điều 100. Quy định khác\nNgười gián tiếp liên quan bị tử hình.\n"
        "Điều 123. Tội giết người\nPhạt tù theo quy định.\n"
        "Điều 124. Quy định khác\nNội dung khác."
    )
    window = web_sources.best_window(text, "Giết người gián tiếp thì bị tử hình hay đi tù")
    assert "Điều 123" in window and "Điều 100" not in window
