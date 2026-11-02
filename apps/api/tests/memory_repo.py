"""In-memory stand-in for BackendRepository. Real queries are covered by the emulator suite."""

import math
from copy import deepcopy

from app.repositories.backend import utcnow

OPS = {
    "==": lambda a, b: a == b,
    "<=": lambda a, b: a is not None and a <= b,
    "in": lambda a, b: a in b,
    "!=": lambda a, b: a != b,
}


class MemoryRepo:
    def __init__(self):
        self.rows = {}

    def get(self, collection, doc_id):
        row = self.rows.get((collection, doc_id))
        return {**deepcopy(row), "id": doc_id} if row is not None else None

    def mutate(self, collection, doc_id, change, *, actor, event, request_id, extra=None):
        current = self.get(collection, doc_id)
        patch = change(current)
        if patch is None:
            return current
        data = {
            **(current or {"createdAt": utcnow()}),
            **patch,
            "updatedAt": utcnow(),
            "version": (current or {}).get("version", 0) + 1,
        }
        data.pop("id", None)
        self.rows[(collection, doc_id)] = data
        for name, row_id, row in extra(patch) if extra else []:
            self.rows[(name, row_id)] = {**row, "createdAt": utcnow()}
        return self.get(collection, doc_id)

    def query(self, collection, filters=(), order=None, limit=100):
        found = [
            self.get(name, doc_id)
            for (name, doc_id), row in sorted(self.rows.items(), key=lambda x: x[0][1])
            if name == collection and all(OPS[op](row.get(f), v) for f, op, v in filters)
        ]
        if order:
            found.sort(key=lambda row: row[order])
        return found[:limit]

    def scan(self, collection, filters=(), batch_size=100):
        yield from self.query(collection, filters, limit=10**6)

    def put(self, collection, doc_id, data):
        self.rows[(collection, doc_id)] = deepcopy(data)

    def put_many(self, collection, rows):
        for doc_id, data in rows.items():
            self.put(collection, doc_id, data)

    def remove(self, collection, doc_id):
        self.rows.pop((collection, doc_id), None)

    def nearest(self, collection, filters, vector, limit):
        def cosine(other):
            other = list(other)
            top = sum(a * b for a, b in zip(vector, other))
            return top / (math.hypot(*vector) * math.hypot(*other))

        rows = self.query(collection, filters, limit=10**6)
        for row in rows:
            row["distance"] = 1 - cosine(row["vector"])
        return sorted(rows, key=lambda row: row["distance"])[:limit]


class FakeBlob:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def upload_from_filename(self, path, **_):
        self.store[self.name] = open(path, "rb").read()

    def upload_from_string(self, data, **_):
        self.store[self.name] = data

    def download_to_filename(self, path, **_):
        open(path, "wb").write(self.store[self.name])

    def reload(self, **_):
        pass

    def delete(self, **_):
        self.store.pop(self.name, None)

    generation = 1


class FakeBucket:
    def __init__(self):
        self.store = {}

    def blob(self, name):
        return FakeBlob(self.store, name)

    def list_blobs(self, prefix="", **_):
        return [FakeBlob(self.store, n) for n in list(self.store) if n.startswith(prefix)]
