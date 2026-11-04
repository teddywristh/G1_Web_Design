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


def page(text, image=True):
    return SimpleNamespace(extract_text=lambda: text, images=[1] if image else [])


def test_repeated_watermark_ocr_and_text_pages_are_preserved(monkeypatch):
    pdf = PDF([page('w\nw\nw\nWatermark.example') for _ in range(4)] + [page('Điều 1. Văn bản số có nội dung đầy đủ', False)])
    monkeypatch.setattr(parser.pdfplumber, 'open', lambda _: pdf)
    calls = []
    monkeypatch.setattr(parser, 'ocr_page', lambda path, number, settings, heartbeat: calls.append(number) or 'Điều 2. Nội dung đã nhận dạng')
    pages = parser.extract_pages('doc.pdf', 10, SimpleNamespace(ocr_enabled=True))
    assert calls == [1, 2, 3, 4]
    assert pages[-1] == 'Điều 1. Văn bản số có nội dung đầy đủ'


def test_scanned_pages_are_not_published_when_ocr_unavailable(monkeypatch):
    monkeypatch.setattr(parser.pdfplumber, 'open', lambda _: PDF([page('')]))
    monkeypatch.setattr(parser, 'ocr_page', lambda *_: (_ for _ in ()).throw(NeedsOCR()))
    with pytest.raises(NeedsOCR):
        parser.extract_pages('doc.pdf', 10, SimpleNamespace(ocr_enabled=True))
