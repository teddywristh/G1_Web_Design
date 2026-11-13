"""Incremental reader for the model's JSON answer.

The model emits one JSON object whose "claims" array holds the answer. ClaimStream is fed the raw
text as it arrives and returns each claim the moment its closing brace is seen, so the caller can
validate and show claims one by one instead of waiting for the whole document. It only locates
claim objects; every claim is still validated by the caller and the complete output is parsed and
checked again once the stream ends.
"""

import json
import re

STATUS = re.compile(r'"status"\s*:\s*"([a-z_]+)"')
ASSUMPTIONS = re.compile(r'"assumptions"\s*:\s*\[\s*"')


class ClaimStream:
    def __init__(self):
        self.text = ""
        self.i = 0
        self.depth = 0
        self.in_str = False
        self.escaped = False
        self.str_start = 0
        self.last_str = None  # string that just ended and may turn out to be an object key
        self.key = None  # key whose value is being read at depth 1
        self.claims_depth = 0  # depth of the "claims" array, 0 until it opens
        self.claims_closed = False
        self.obj_start = None

    @property
    def status(self):
        """Value of "status" once it has been written (it precedes the claims in the schema)."""
        found = STATUS.search(self.text[: self._claims_at()])
        return found.group(1) if found else None

    @property
    def has_assumptions(self):
        return bool(ASSUMPTIONS.search(self.text[: self._claims_at()]))

    def _claims_at(self):
        at = self.text.find('"claims"')
        return len(self.text) if at < 0 else at

    def feed(self, chunk):
        """Add text; return the list of claim dicts completed by it."""
        self.text += chunk
        done = []
        n = len(self.text)
        while self.i < n:
            c = self.text[self.i]
            self.i += 1
            if self.in_str:
                if self.escaped:
                    self.escaped = False
                elif c == "\\":
                    self.escaped = True
                elif c == '"':
                    self.in_str = False
                    if self.depth == 1:
                        self.last_str = self.text[self.str_start : self.i - 1]
                continue
            if c == '"':
                self.in_str = True
                self.str_start = self.i
                continue
            if c == ":" and self.depth == 1:
                self.key = self.last_str
            elif c == "," and self.depth == 1:
                self.key = None
            if not c.isspace() and c != ":":
                self.last_str = None
            if c in "{[":
                self.depth += 1
                if c == "[" and self.depth == 2 and self.key == "claims":
                    self.claims_depth = 2
                elif c == "{" and self.claims_depth and self.depth == self.claims_depth + 1:
                    self.obj_start = self.i - 1
            elif c in "}]":
                if c == "}" and self.obj_start is not None and self.depth == self.claims_depth + 1:
                    try:
                        claim = json.loads(self.text[self.obj_start : self.i])
                    except ValueError:
                        claim = None
                    self.obj_start = None
                    if isinstance(claim, dict):
                        done.append(claim)
                elif c == "]" and self.claims_depth and self.depth == self.claims_depth:
                    self.claims_depth, self.claims_closed = 0, True
                self.depth -= 1
        return done
