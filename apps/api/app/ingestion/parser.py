import os
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path

import pdfplumber

from app.ingestion.validation import NeedsOCR, PermanentError


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
        _run(["pdftoppm", "-f", str(number), "-l", str(number), "-singlefile", "-r", "200", "-png", path, target], heartbeat)
        env = os.environ.copy()
        if settings.ocr_tessdata_dir:
            env["TESSDATA_PREFIX"] = settings.ocr_tessdata_dir
        output = _run([settings.ocr_binary, target + ".png", "stdout", "-l", settings.ocr_languages], heartbeat, env)
        return output.decode("utf-8", errors="replace")


def extract_pages(path, max_pages, settings=None, heartbeat=None):
    """Extract text and OCR image pages with absent or repeated watermark-only text."""
    try:
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > max_pages:
                raise PermanentError("too_many_pages")
            pages = [page.extract_text() or "" for page in pdf.pages]
            images = [bool(page.images) for page in pdf.pages]
    except PermanentError:
        raise
    except Exception:
        raise PermanentError("unsupported_pdf") from None
    normalized = [" ".join(text.split()) for text in pages]
    counts = Counter(normalized)
    candidates = [
        index for index, text in enumerate(normalized)
        if images[index] and (len(text) < 20 or (len(text) < 120 and counts[text] >= 3 and counts[text] > len(pages) * 0.5))
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
    return pages
