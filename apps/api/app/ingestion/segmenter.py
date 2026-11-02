import re
from bisect import bisect_right

CHAPTER = re.compile(r"^\s*Chương\s+([IVXLC\d]+)", re.IGNORECASE)
ARTICLE = re.compile(r"^\s*Điều\s+(\d+)\s*[.:]?", re.IGNORECASE)
CLAUSE = re.compile(r"^\s*(\d+)\.\s+\S")
APPENDIX = re.compile(r"^\s*PHỤ LỤC", re.IGNORECASE)


def join_pages(pages):
    """Full text plus the start offset of every page."""
    starts, text = [], ""
    for page in pages:
        starts.append(len(text))
        text += page + "\n"
    return text, starts


def split_long(text, limit):
    parts, current = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:limit])
            line = line[limit:]
        if current and len(current) + len(line) + 1 > limit:
            parts.append(current)
            current = ""
        current = current + "\n" + line if current else line
    if current:
        parts.append(current)
    return parts


def segment(pages, max_chars):
    """Split pages into chapter/article/clause provisions with page and character spans."""
    text, starts = join_pages(pages)
    blocks = []  # each block: dict(article, clause, chapter, start, lines)
    chapter, article, clause, current = None, None, None, None
    appendix = 0
    offset = 0

    def begin(identifier, start):
        nonlocal current
        current = {
            "identifier": identifier,
            "articleNo": article,
            "clauseNo": clause,
            "chapter": chapter,
            "start": start,
            "end": start,
            "lines": [],
        }
        blocks.append(current)

    for line in text.split("\n"):
        start, end = offset, offset + len(line)
        offset = end + 1
        if not line.strip():
            continue
        if CHAPTER.match(line):
            chapter = CHAPTER.match(line).group(1)
            continue
        if APPENDIX.match(line):
            appendix += 1
            article, clause = None, None
            begin(f"phuluc-{appendix}", start)
        elif ARTICLE.match(line):
            article, clause = ARTICLE.match(line).group(1), None
            begin(f"dieu-{article}", start)
        elif article and CLAUSE.match(line):
            clause = CLAUSE.match(line).group(1)
            begin(f"dieu-{article}/khoan-{clause}", start)
        elif current is None:
            begin("preamble", start)
        current["lines"].append(line)
        current["end"] = end

    if not any(block["articleNo"] for block in blocks):
        blocks = group_paragraphs(text, max_chars)

    provisions = []
    for block in blocks:
        body = "\n".join(block["lines"]) if "lines" in block else block["text"]
        pieces = split_long(body, max_chars)
        for number, piece in enumerate(pieces, 1):
            provisions.append(
                {
                    "identifier": block["identifier"],
                    "article": f"Điều {block['articleNo']}" if block["articleNo"] else None,
                    "articleNo": block["articleNo"],
                    "clause": f"Khoản {block['clauseNo']}" if block["clauseNo"] else None,
                    "clauseNo": block["clauseNo"],
                    "chapter": block["chapter"],
                    "text": piece,
                    "part": number,
                    "startChar": block["start"],
                    "endChar": block["end"],
                    "pageStart": bisect_right(starts, block["start"]),
                    "pageEnd": bisect_right(starts, block["end"]),
                }
            )
    return provisions


def group_paragraphs(text, max_chars):
    """Fallback for documents without recognizable articles."""
    blocks, offset, group = [], 0, None
    for paragraph in text.split("\n\n"):
        start = text.find(paragraph, offset)
        offset = start + len(paragraph)
        if not paragraph.strip():
            continue
        if group and len(group["text"]) + len(paragraph) < max_chars:
            group["text"] += "\n" + paragraph
            group["end"] = offset
            continue
        group = {
            "identifier": f"p{len(blocks) + 1}",
            "articleNo": None,
            "clauseNo": None,
            "chapter": None,
            "start": start,
            "end": offset,
            "text": paragraph,
        }
        blocks.append(group)
    return blocks
