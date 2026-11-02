"""Official-source and example search. Fetched pages are data, never instructions."""

import io
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
import pdfplumber

from app.core.errors import APIError

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
ARTICLE = re.compile(r"^\s*Điều\s+\d+", re.IGNORECASE | re.MULTILINE)


def host_allowed(host, domains):
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def check_public_host(host):
    """Reject private, loopback, link-local (cloud metadata) and reserved addresses."""
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, 443)}
    except OSError:
        raise APIError(502, "fetch_failed", "Source host cannot be resolved") from None
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise APIError(403, "fetch_blocked", "Source address is not public")


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip -= 1
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def to_text(body, content_type):
    if "pdf" in content_type:
        with pdfplumber.open(io.BytesIO(body)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages[:50])
    parser = TextExtractor()
    parser.feed(body.decode("utf-8", errors="replace"))
    return re.sub(r"\n\s*\n+", "\n\n", "".join(parser.parts)).strip()


def fetch(url, settings, domains=None, transport=None):
    """HTTPS only; every redirect is validated again; size and time are bounded."""
    for _ in range(MAX_REDIRECTS + 1):
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host:
            raise APIError(403, "fetch_blocked", "Only https sources are allowed")
        if domains is not None and not host_allowed(host, domains):
            raise APIError(403, "fetch_blocked", "Source domain is not allowed")
        if transport is None:
            check_public_host(host)
        with httpx.Client(
            timeout=10, transport=transport, follow_redirects=False, trust_env=False
        ) as client:
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get("location", ""))
                    continue
                content_type = response.headers.get("content-type", "").lower()
                if response.status_code != 200 or not any(
                    kind in content_type for kind in ("html", "text/plain", "pdf")
                ):
                    raise APIError(502, "fetch_failed", "Source could not be read")
                body = b""
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise APIError(502, "fetch_failed", "Source is too large")
        return url, to_text(body, content_type)
    raise APIError(502, "fetch_failed", "Too many redirects")


def best_window(text, query, size=1500):
    """Paragraph window that shares the most words with the query."""
    words = set(re.findall(r"\w+", query.casefold()))
    best, best_score = text[:size], -1
    for paragraph in text.split("\n"):
        score = len(words & set(re.findall(r"\w+", paragraph.casefold())))
        if score > best_score and paragraph.strip():
            best, best_score = paragraph.strip()[:size], score
    return best


def search_urls(client, model, query, domains=None):
    """Hosted web search through the already-selected OpenAI client."""
    tool = {"type": "web_search"}
    if domains:
        tool["filters"] = {"allowed_domains": domains}
    response = client.responses.create(model=model, input=query, tools=[tool])
    urls = []
    for item in response.output:
        for part in getattr(item, "content", None) or []:
            for note in getattr(part, "annotations", None) or []:
                if getattr(note, "type", "") == "url_citation" and note.url not in urls:
                    urls.append(note.url)
    return urls


def classify(host, text, settings):
    if host_allowed(host, settings.official_domains):
        return "official_legal_text" if len(ARTICLE.findall(text)) >= 3 else "official_guidance"
    return "commentary"


def web_item(url, text, query, source_type):
    host = urlparse(url).hostname or url
    return {
        "provisionVersionId": None,
        "kbId": None,
        "title": host,
        "number": "",
        "identifier": "",
        "article": None,
        "clause": None,
        "chapter": None,
        "text": best_window(text, query),
        "sourceType": source_type,
        "sourceUrl": url,
        "limitations": ["web_validity_unverified"],
        "score": 0.0,
        "via": "web",
    }


def gather(ai, settings, query, mode, budget, transport=None):
    """Returns (items, limitations). budget counts searches and fetches already allowed."""
    client = getattr(ai, "client", None)
    if client is None:
        return [], ["web_unavailable_for_provider"]
    items, limits = [], []
    plans = []
    if settings.official_web_enabled and budget["searches"] < settings.max_official_searches:
        plans.append((query, settings.official_domains, settings.official_domains))
    if mode == "examples" and settings.example_search_enabled:
        plans.append(("ví dụ thực tế, bản án, tình huống: " + query, None, None))
    for text, search_domains, fetch_domains in plans:
        budget["searches"] += 1
        try:
            urls = search_urls(client, settings.default_llm_model, text, search_domains)
        except Exception:
            limits.append("web_search_unavailable")
            continue
        for url in urls:
            if budget["fetches"] >= settings.max_fetched_sources:
                break
            budget["fetches"] += 1
            try:
                final_url, body = fetch(url, settings, fetch_domains, transport)
            except APIError:
                limits.append("web_source_unreadable")
                continue
            host = urlparse(final_url).hostname or ""
            items.append(web_item(final_url, body, query, classify(host, body, settings)))
    return items, limits
