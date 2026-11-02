import pdfplumber

from app.ingestion.validation import PermanentError


def extract_pages(path, max_pages):
    """Plain per-page text of a text PDF."""
    try:
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > max_pages:
                raise PermanentError("too_many_pages")
            return [page.extract_text() or "" for page in pdf.pages]
    except PermanentError:
        raise
    except Exception:
        raise PermanentError("unsupported_pdf") from None
