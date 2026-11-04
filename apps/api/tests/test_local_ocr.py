from types import SimpleNamespace

import pytest

from app.ingestion import parser
from app.ingestion.validation import NeedsOCR


class PDF:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def close(self):
        pass


def page(text, image=True):
    return SimpleNamespace(extract_text=lambda: text, images=[1] if image else [])


def test_repeated_watermark_ocr_and_text_pages_are_preserved(monkeypatch):
    pdf = PDF(
        [page("w\nw\nw\nWatermark.example") for _ in range(4)]
        + [page("Điều 1. Văn bản số có nội dung đầy đủ", False)]
    )
    monkeypatch.setattr(parser.pdfplumber, "open", lambda _: pdf)
    calls = []
    monkeypatch.setattr(
        parser,
        "ocr_page",
        lambda path, number, settings, heartbeat: (
            calls.append(number) or "Điều 2. Nội dung đã nhận dạng"
        ),
    )
    pages = parser.extract_pages("doc.pdf", 10, SimpleNamespace(ocr_enabled=True))
    assert calls == [1, 2, 3, 4]
    assert pages[-1] == "Điều 1. Văn bản số có nội dung đầy đủ"


def test_scanned_pages_are_not_published_when_ocr_unavailable(monkeypatch):
    monkeypatch.setattr(parser.pdfplumber, "open", lambda _: PDF([page("")]))
    monkeypatch.setattr(parser, "ocr_page", lambda *_: (_ for _ in ()).throw(NeedsOCR()))
    with pytest.raises(NeedsOCR):
        parser.extract_pages("doc.pdf", 10, SimpleNamespace(ocr_enabled=True))


def test_single_page_broken_watermark_triggers_ocr(monkeypatch):
    monkeypatch.setattr(parser.pdfplumber, "open", lambda _: PDF([page("w w w n v m a t L u at")]))
    monkeypatch.setattr(parser, "ocr_page", lambda *_: "Điều 1. Phạm vi của Bộ luật này")
    assert parser.extract_pages("doc.pdf", 10, SimpleNamespace(ocr_enabled=True))[0].startswith(
        "Điều 1"
    )


def test_good_digital_text_does_not_call_ocr(monkeypatch):
    text = "Điều 1. Bộ luật này quy định về quyền và nghĩa vụ của cá nhân."
    monkeypatch.setattr(parser.pdfplumber, "open", lambda _: PDF([page(text, True)]))
    monkeypatch.setattr(parser, "ocr_page", lambda *_: pytest.fail("unexpected OCR"))
    assert parser.extract_pages("doc.pdf", 10, SimpleNamespace(ocr_enabled=True)) == [text]


def test_paddle_service_receives_rendered_page(monkeypatch):
    from pathlib import Path

    calls = []

    def render(command, heartbeat=None, env=None):
        calls.append(command)
        Path(command[-1] + ".png").write_bytes(b"png")

    def send(url, content, headers, timeout, trust_env):
        calls.append((url, content))
        return SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"text": "Điều 12. Quy định"},
        )

    monkeypatch.setattr(parser, "_run", render)
    monkeypatch.setattr(parser.httpx, "post", send)
    settings = SimpleNamespace(ocr_service_url="http://127.0.0.1:8011", ocr_timeout_seconds=30)
    assert parser.ocr_page("doc.pdf", 7, settings) == "Điều 12. Quy định"
    assert calls[0][1:5] == ["-f", "7", "-l", "7"]
    assert calls[1] == ("http://127.0.0.1:8011/v1/ocr", b"png")


def test_paddle_output_with_lost_accents_uses_better_cpu_result(monkeypatch):
    from pathlib import Path

    def render(command, heartbeat=None, env=None):
        if command[0] == "pdftoppm":
            Path(command[-1] + ".png").write_bytes(b"png")
            return b""
        return ("Điều 1. Quy định về quyền và nghĩa vụ của cá nhân. " * 10).encode()

    monkeypatch.setattr(parser, "_run", render)
    monkeypatch.setattr(
        parser.httpx,
        "post",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"text": "Diu 1. Quy dinh ve quyen va nghia vu cua ca nhan. " * 10},
        ),
    )
    settings = SimpleNamespace(
        ocr_service_url="http://127.0.0.1:8011",
        ocr_timeout_seconds=30,
        ocr_fallback_binary="tesseract",
    )
    assert "Điều 1." in parser.ocr_page("doc.pdf", 1, settings)
