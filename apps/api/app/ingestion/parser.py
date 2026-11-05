import re
import subprocess
import tempfile
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path

import httpx
import pdfplumber

from app.core.errors import APIError
from app.ingestion.validation import NeedsOCR, PermanentError

VIETNAMESE_MARKS = frozenset("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ")


def accent_ratio(text):
    letters = [c for c in text.lower() if c.isalpha()]
    return sum(c in VIETNAMESE_MARKS for c in letters) / len(letters) if letters else 0.0


def _run(command, heartbeat=None, env=None):
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    except OSError:
        raise NeedsOCR() from None
    try:
        deadline = time.monotonic() + 180
        while True:
            try:
                output, _ = process.communicate(timeout=10)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    raise NeedsOCR()
                if heartbeat:
                    heartbeat()
        if process.returncode:
            raise NeedsOCR()
        return output
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


def ocr_page(path, number, settings, heartbeat=None):
    with tempfile.TemporaryDirectory(prefix="legal-ocr-") as directory:
        target = str(Path(directory) / "page")
        _run(
            [
                "pdftoppm",
                "-f",
                str(number),
                "-l",
                str(number),
                "-singlefile",
                "-r",
                "200",
                "-png",
                path,
                target,
            ],
            heartbeat,
        )

        def request_ocr():
            try:
                with open(target + ".png", "rb") as image:
                    response = httpx.post(
                        settings.ocr_service_url.rstrip("/") + "/v1/ocr",
                        content=image.read(),
                        headers={"Content-Type": "image/png"},
                        timeout=settings.ocr_timeout_seconds,
                        trust_env=False,
                    )
                if response.status_code == 429:
                    raise APIError(503, "ocr_unavailable", "OCR service busy")
                response.raise_for_status()
                text = response.json()["text"]
                if not isinstance(text, str):
                    raise ValueError("invalid OCR response")
                return text
            except APIError:
                raise
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                raise APIError(503, "ocr_unavailable", "OCR service unavailable") from None

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(request_ocr)
            while True:
                try:
                    paddle_text = future.result(timeout=10)
                    break
                except FutureTimeout:
                    if heartbeat:
                        heartbeat()
        if len(paddle_text) >= 150 and accent_ratio(paddle_text) < 0.18:
            try:
                fallback = _run(
                    [settings.ocr_fallback_binary, target + ".png", "stdout", "-l", "vie+eng"],
                    heartbeat,
                ).decode("utf-8", errors="replace")
                if accent_ratio(fallback) > max(0.18, accent_ratio(paddle_text) * 1.3):
                    return fallback
            except NeedsOCR:
                pass
        return paddle_text


def normalize_page(text):
    # Giữ ranh giới điều khoản, chỉ nối dòng mềm trong cùng đoạn.
    text = unicodedata.normalize("NFC", text).replace("\u00ad", "").replace("\r\n", "\n")
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    result = []
    heading = re.compile(r"^(?:Điều\s+\d|Chương\s+|Mục\s+|PHỤ LỤC|\d+[.)]\s|[a-zđ][)]\s)", re.I)
    for line in lines:
        if (
            result
            and result[-1]
            and line
            and not heading.match(line)
            and not heading.match(result[-1])
            and not re.search(r"[.!?:;]$", result[-1])
        ):
            result[-1] += " " + line
        else:
            result.append(line)
    return "\n".join(result)


def extract_pages(path, max_pages, settings=None, heartbeat=None):
    """Extract text and OCR image pages with absent or repeated watermark-only text."""
    try:
        pdf = pdfplumber.open(path)
    except Exception:
        raise PermanentError("unsupported_pdf") from None
    try:
        if len(pdf.pages) > max_pages:
            raise PermanentError("too_many_pages")
        pages, images = [], []
        for page in pdf.pages:
            if heartbeat:
                heartbeat()
            try:
                pages.append(page.extract_text() or "")
                images.append(bool(page.images))
            except Exception:
                raise PermanentError("unsupported_pdf") from None
    finally:
        pdf.close()
    normalized = [" ".join(text.split()) for text in pages]
    counts = Counter(normalized)
    candidates = [
        index
        for index, text in enumerate(normalized)
        if images[index]
        and (
            len(text) < 20
            or (
                len(text) < 120
                and sum(len(word) <= 2 for word in text.split()) >= 6
                and sum(len(word) <= 2 for word in text.split()) / len(text.split()) >= 0.7
            )
            or (len(text) < 120 and counts[text] >= 3 and counts[text] > len(pages) * 0.5)
        )
    ]
    if candidates and settings and settings.ocr_enabled:
        for index in candidates:
            if heartbeat:
                heartbeat()
            pages[index] = ocr_page(str(path), index + 1, settings, heartbeat)
        if any(len(pages[index].strip()) < 20 for index in candidates):
            raise NeedsOCR()
    elif candidates:
        raise NeedsOCR()
    return [normalize_page(text) for text in pages]
