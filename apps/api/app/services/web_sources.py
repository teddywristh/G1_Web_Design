"""Official-source and example search. Fetched pages are data, never instructions."""

import io
import ipaddress
import logging
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlparse

import httpx
import pdfplumber

from app.core.errors import APIError

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
logger = logging.getLogger("legal_api")
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
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
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


def fetch(url, settings, domains=None, transport=None, links=False):
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
        if links:
            if "html" not in content_type:
                raise APIError(502, "fetch_failed", "Search page is not HTML")
            parser = TextExtractor()
            parser.feed(body.decode("utf-8", errors="replace"))
            return url, parser.links
        return url, to_text(body, content_type)
    raise APIError(502, "fetch_failed", "Too many redirects")


def best_window(text, query, size=1500):
    """Paragraph window that shares the most words with the query."""
    tokens = re.findall(r"\w+", query.casefold())
    stop = {
        "có",
        "bị",
        "đi",
        "hay",
        "thì",
        "không",
        "những",
        "được",
        "trong",
        "nào",
        "thế",
        "nhiêu",
        "về",
        "là",
        "của",
        "tôi",
        "muốn",
        "hỏi",
    }
    topic = [token for token in tokens if token not in stop]
    phrase = " ".join(topic[:2]) if len(topic) >= 2 else ""
    words = {w for w in tokens if len(w) > 2 and w not in stop}

    def score(section):
        lower = " ".join(section.casefold().split())
        return len(words & set(re.findall(r"\w+", lower))) + (
            8 if phrase and phrase in lower else 0
        )

    articles = list(ARTICLE.finditer(text))
    if articles:
        sections = [
            text[
                item.start() : articles[i + 1].start()
                if i + 1 < len(articles)
                else item.start() + 4000
            ]
            for i, item in enumerate(articles)
        ]
        best = max(sections, key=score)
        if words & set(re.findall(r"\w+", best.casefold())):
            return best[: max(size, 3000)]
    best, best_score = text[:size], -1
    for paragraph in text.split("\n"):
        rank = score(paragraph)
        if rank > best_score and paragraph.strip():
            best, best_score = paragraph.strip()[:size], rank
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


def brave_search_urls(key, query, domains):
    """Search only public sites; never include document contents or credentials in the query."""
    sites = " OR ".join("site:" + domain for domain in domains)
    with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
        response = client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": f"{query} ({sites})", "count": 10},
            headers={"Accept": "application/json", "X-Subscription-Token": key},
        )
        response.raise_for_status()
        rows = response.json().get("web", {}).get("results", [])
    return [row["url"] for row in rows if isinstance(row, dict) and isinstance(row.get("url"), str)]


def vbpl_search_urls(query, settings, transport=None):
    """Use the public VBPL search page without an API key."""
    stop = {
        "những",
        "thông",
        "tin",
        "nào",
        "được",
        "trong",
        "theo",
        "về",
        "là",
        "của",
        "có",
        "cần",
        "gì",
        "như",
        "thế",
    }
    words = [
        word
        for word in re.findall(r"[\w/-]+", query.casefold())
        if (len(word) > 1 or word == "ý") and word not in stop
    ]
    keyword = " ".join(words[:6]) or query[:100]
    url = "https://vbpl.vn/TW/Pages/vbpq-timkiem.aspx?" + urlencode(
        {"Keyword": keyword, "SearchIn": "VBPQFulltext", "s": "1", "type": "0"}
    )
    base, links = fetch(url, settings, ["vbpl.vn"], transport, links=True)
    found = []
    for href in links:
        candidate = urljoin(base, href)
        parsed = urlparse(candidate)
        if (
            parsed.scheme == "https"
            and parsed.hostname == "vbpl.vn"
            and "vbpq-toanvan.aspx" in parsed.path.lower()
            and candidate not in found
        ):
            found.append(candidate)
    return found[: settings.max_fetched_sources]


def congbao_search_urls(query, settings, transport=None):
    """Search the public Công báo index and return official document PDFs."""
    stop = {
        "bạn",
        "xem",
        "giúp",
        "mình",
        "tôi",
        "cho",
        "biết",
        "nhưng",
        "những",
        "thông",
        "tin",
        "nào",
        "được",
        "trong",
        "theo",
        "về",
        "là",
        "của",
        "có",
        "cần",
        "gì",
        "như",
        "thế",
        "không",
        "bị",
        "đi",
        "tù",
        "bao",
        "nhiêu",
        "thì",
        "hay",
    }
    words = [
        word
        for word in re.findall(r"[\w/-]+", query.casefold())
        if (len(word) > 1 or word == "ý") and word not in stop
    ]
    keywords = list(dict.fromkeys([" ".join(words[:5]) or query[:100], " ".join(words[:2])]))
    with httpx.Client(
        timeout=10, transport=transport, follow_redirects=False, trust_env=False
    ) as client:
        documents = []
        for keyword in keywords[:2]:
            if not keyword:
                continue
            response = client.post(
                "https://api-searchcongbao.chinhphu.vn/search/all",
                json={"filters": {}, "page": 1, "page_size": 20, "query": keyword},
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("success") or not isinstance(data.get("data"), list):
                raise APIError(502, "fetch_failed", "Official search unavailable")
            documents = [
                item["data"]
                for item in data["data"]
                if item.get("type") == "van_ban"
                and isinstance(item.get("data"), dict)
                and any(
                    f.get("file_extension", "").lower() == "pdf"
                    for f in item["data"].get("danh_sach_tep_van_ban", [])
                )
            ]
            if documents:
                break
    documents.sort(
        key=lambda doc: (
            doc.get("score") or 0,
            doc.get("loai_van_ban") == "Văn bản hợp nhất",
            doc.get("ngay_ban_hanh") or "",
        ),
        reverse=True,
    )
    urls = []
    for doc in documents:
        for file in doc.get("danh_sach_tep_van_ban", []):
            url = file.get("duong_dan", "")
            parsed = urlparse(url)
            if (
                file.get("file_extension", "").lower() == "pdf"
                and parsed.scheme == "https"
                and parsed.hostname == "congbaocdn.chinhphu.vn"
                and url not in urls
            ):
                urls.append(url)
                if len(urls) >= settings.max_fetched_sources:
                    return urls
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
    brave_key = settings.brave_search_api_key.get_secret_value()
    items, limits = [], []
    plans = []
    if settings.official_web_enabled and budget["searches"] < settings.max_official_searches:
        plans.append((query, settings.official_domains, settings.official_domains))
    if mode == "examples" and settings.example_search_enabled:
        plans.append(("ví dụ thực tế, bản án, tình huống: " + query, None, None))
    for text, search_domains, fetch_domains in plans:
        budget["searches"] += 1
        try:
            if brave_key and search_domains:
                urls = brave_search_urls(brave_key, text, search_domains)
            elif search_domains:
                try:
                    urls = congbao_search_urls(text, settings, transport)
                except (APIError, httpx.HTTPError, ValueError):
                    urls = vbpl_search_urls(text, settings, transport)
            elif client is not None:
                model = getattr(
                    getattr(ai, "settings", None), "default_llm_model", settings.default_llm_model
                )
                urls = search_urls(client, model, text, search_domains)
            else:
                limits.append("web_unavailable_for_provider")
                continue
        except Exception:
            limits.append("web_search_unavailable")
            continue
        if not urls:
            limits.append("web_no_results")
        for url in urls:
            if budget["fetches"] >= budget.get("fetch_limit", settings.max_fetched_sources):
                break
            budget["fetches"] += 1
            try:
                final_url, body = fetch(url, settings, fetch_domains, transport)
            except (APIError, httpx.HTTPError, ValueError) as exc:
                logger.warning(
                    "web_source_unreadable host=%s error=%s",
                    urlparse(url).hostname or "unknown",
                    getattr(exc, "code", type(exc).__name__),
                )
                limits.append("web_source_unreadable")
                continue
            host = urlparse(final_url).hostname or ""
            items.append(web_item(final_url, body, query, classify(host, body, settings)))
    return items, limits
