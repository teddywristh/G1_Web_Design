class PermanentError(Exception):
    """The input cannot be processed; retrying will not help."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class NeedsOCR(Exception):
    pass


class Cancelled(Exception):
    """The source was deleted or replaced while the job was running."""


MIN_PAGE_CHARS = 20


def check_pages(pages, ocr_enabled):
    """Never publish a document whose pages were silently lost."""
    blank = [number for number, text in enumerate(pages, 1) if len(text.strip()) < MIN_PAGE_CHARS]
    quality = {"pages": len(pages), "blankPages": blank}
    if not pages:
        raise PermanentError("empty_pdf")
    if len(blank) > 0.2 * len(pages) and not ocr_enabled:
        raise NeedsOCR()
    return quality


def check_structure(provisions):
    """Warnings for odd numbering; they are recorded, not silently fixed."""
    warnings = []
    seen = set()
    last = 0
    for item in provisions:
        if item["part"] > 1 or item["articleNo"] is None or item["clauseNo"] is not None:
            continue
        number = int(item["articleNo"])
        if item["identifier"] in seen:
            warnings.append("duplicate_article:" + item["articleNo"])
        elif number != last + 1 and last:
            warnings.append(f"article_gap:{last}->{number}")
        seen.add(item["identifier"])
        last = number
    if not any(item["articleNo"] for item in provisions):
        warnings.append("unstructured_document")
    return warnings
