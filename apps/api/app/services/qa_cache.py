"""Answer cache for repeated questions.

An entry is only reused when everything that shaped the answer is identical: the knowledge bases
and their *published generation*, the as-of date, the normalised question, the model and the
policy version. Publishing a new corpus changes the generation, so stale answers become
unreachable by construction. Reuse is also gated by the caller: the cited provisions are re-read
and must still be alive and applicable before a cached answer is returned.

The cache is per process and bounded; it holds public legal text and the model's own answer, never
credentials. Only answers backed purely by the knowledge base are stored (no web content).
"""

import hashlib
import re
import threading
import time
from collections import OrderedDict

from app.services.documents import normalize


class AnswerCache:
    def __init__(self):
        self.rows = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key, ttl):
        with self.lock:
            row = self.rows.get(key)
            if row is None:
                return None
            if time.monotonic() - row["at"] > ttl:
                del self.rows[key]
                return None
            self.rows.move_to_end(key)
            return row

    def put(self, key, value, limit):
        with self.lock:
            self.rows[key] = {**value, "at": time.monotonic()}
            self.rows.move_to_end(key)
            while len(self.rows) > limit:
                self.rows.popitem(last=False)

    def discard(self, key):
        with self.lock:
            self.rows.pop(key, None)

    def clear(self):
        with self.lock:
            self.rows.clear()


CACHE = AnswerCache()


def canonical(question):
    """Case, accents, punctuation and spacing do not change what is being asked."""
    text = re.sub(r"[^\w\s/]", " ", normalize(question))
    return " ".join(text.split())


def key_for(kbs, request, as_of, policy):
    scope = sorted((kb["id"], kb["generation"] or "") for kb in kbs)
    raw = "|".join(
        [
            policy,
            repr(scope),
            as_of.isoformat(),
            request.retrieval_mode,
            request.web_mode,
            str(request.top_k),
            request.provider,
            request.model or "",
            request.effort,
            canonical(request.question),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()
