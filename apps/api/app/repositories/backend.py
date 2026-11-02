"""Bounded Firestore queries and transactional mutations with atomic audit logs."""

import base64
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from google.api_core.datetime_helpers import DatetimeWithNanoseconds, to_rfc3339
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.vector import Vector

from app.core.errors import APIError


def fingerprint(collection, filters, order):
    raw = json.dumps([collection, filters, order], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def encode_cursor(scope, value, doc_id):
    if isinstance(value, datetime):
        stamp = value.rfc3339() if isinstance(value, DatetimeWithNanoseconds) else to_rfc3339(value)
        value = {"timestamp": stamp}
    raw = json.dumps({"scope": scope, "value": value, "id": doc_id}).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor, scope):
    try:
        data = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if data["scope"] != scope or not isinstance(data["id"], str):
            raise ValueError()
        if not data["id"] or "/" in data["id"] or len(data["id"]) > 1500:
            raise ValueError()
        value = data["value"]
        if isinstance(value, dict):
            value = DatetimeWithNanoseconds.from_rfc3339(value["timestamp"])
            if value.tzinfo is None:
                raise ValueError()
        elif not isinstance(value, str):
            raise ValueError()
        return value, data["id"]
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        raise APIError(422, "invalid_cursor", "Cursor is invalid for this query") from exc


class BackendRepository:
    def __init__(self, db):
        self.db = db

    def get(self, collection, doc_id):
        snap = self.db.collection(collection).document(doc_id).get(timeout=5, retry=None)
        return {**snap.to_dict(), "id": snap.id} if snap.exists else None

    def mutate(self, collection, doc_id, change, *, actor, event, request_id, extra=None):
        """Callback receives current state; data and success audit commit together.

        extra(patch) may return (collection, doc_id, data) rows written in the same
        transaction, used for the job outbox.
        """
        ref = self.db.collection(collection).document(doc_id)
        audit = self.db.collection("system_logs").document(uuid4().hex)

        @firestore.transactional
        def commit(transaction):
            snap = ref.get(transaction=transaction, timeout=5, retry=None)
            current = {**snap.to_dict(), "id": snap.id} if snap.exists else None
            patch = change(current)
            if patch is None:  # idempotent retry; no mutation or duplicate audit
                return
            patch = {
                **patch,
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "version": (current or {}).get("version", 0) + 1,
            }
            if current is None:
                transaction.create(ref, {**patch, "createdAt": firestore.SERVER_TIMESTAMP})
            else:
                transaction.update(ref, patch)
            for name, row_id, data in extra(patch) if extra else []:
                transaction.set(
                    self.db.collection(name).document(row_id),
                    {**data, "createdAt": firestore.SERVER_TIMESTAMP},
                )
            transaction.create(
                audit,
                {
                    "event": event,
                    "actorId": actor,
                    "targetId": doc_id,
                    "result": "failed" if event.endswith(("_failed", "_expired")) else "success",
                    "requestId": request_id,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                },
            )

        commit(self.db.transaction(max_attempts=3))
        return self.get(collection, doc_id)

    def page(
        self, collection, *, filters=(), order="createdAt", descending=True, limit=20, cursor=None
    ):
        ref = self.db.collection(collection)
        scope = fingerprint(collection, filters, (order, descending))
        query = ref
        for field, op, value in filters:
            query = query.where(filter=FieldFilter(field, op, value))
        direction = "DESCENDING" if descending else "ASCENDING"
        query = query.order_by(order, direction=direction).order_by("__name__", direction=direction)
        if cursor:
            value, doc_id = decode_cursor(cursor, scope)
            if order in {"createdAt", "updatedAt"} and not isinstance(value, datetime):
                raise APIError(422, "invalid_cursor", "Cursor has an invalid sort value")
            if order not in {"createdAt", "updatedAt"} and not isinstance(value, str):
                raise APIError(422, "invalid_cursor", "Cursor has an invalid sort value")
            query = query.start_after({order: value, "__name__": ref.document(doc_id)})
        snapshots = list(query.limit(limit + 1).stream(timeout=5, retry=None))
        items = [{**s.to_dict(), "id": s.id} for s in snapshots[:limit]]
        next_cursor = None
        if len(snapshots) > limit:
            last = items[-1]
            next_cursor = encode_cursor(scope, last[order], last["id"])
        return {"items": items, "nextCursor": next_cursor}

    def query(self, collection, filters=(), order=None, limit=100):
        """Bounded, index-backed read. Never use it for unbounded scans."""
        query = self.db.collection(collection)
        for field, op, value in filters:
            query = query.where(filter=FieldFilter(field, op, value))
        if order:
            query = query.order_by(order)
        snapshots = query.limit(limit).stream(timeout=10, retry=None)
        return [{**s.to_dict(), "id": s.id} for s in snapshots]

    def put(self, collection, doc_id, data):
        """Deterministic derived record; repeating the write is harmless."""
        self.db.collection(collection).document(doc_id).set(data, timeout=10, retry=None)

    def put_many(self, collection, rows):
        items = list(rows.items())
        for start in range(0, len(items), 400):
            batch = self.db.batch()
            for doc_id, data in items[start : start + 400]:
                if isinstance(data.get("vector"), list):
                    data = {**data, "vector": Vector(data["vector"])}
                batch.set(self.db.collection(collection).document(doc_id), data)
            batch.commit(timeout=30, retry=None)

    def remove(self, collection, doc_id):
        self.db.collection(collection).document(doc_id).delete()

    def nearest(self, collection, filters, vector, limit):
        from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

        query = self.db.collection(collection)
        for field, op, value in filters:
            query = query.where(filter=FieldFilter(field, op, value))
        found = query.find_nearest(
            vector_field="vector",
            query_vector=Vector(vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=limit,
            distance_result_field="distance",
        )
        return [{**s.to_dict(), "id": s.id} for s in found.stream(timeout=20, retry=None)]

    def scan(self, collection, *, filters=(), batch_size=100):
        """Maintenance-only bounded pages, without accumulating the collection."""
        ref = self.db.collection(collection)
        query = ref
        for field, op, value in filters:
            query = query.where(filter=FieldFilter(field, op, value))
        query = query.order_by("__name__").limit(batch_size)
        last = None
        while True:
            page = query.start_after(last) if last else query
            snapshots = list(page.stream(timeout=10, retry=None))
            if not snapshots:
                return
            yield from ({**s.to_dict(), "id": s.id} for s in snapshots)
            last = snapshots[-1]


def utcnow():
    return datetime.now(timezone.utc)
