# Q&A latency

Why a simple question used to take 36–46 s, what changed, and how to check it.

## What was measured

Two complete `/rag/ask` runs in `.data/cloud-demo/api.log` took 36.3 s and 46.1 s. Retrieval is not where
the time goes (`experiments/retrieval/results.json`, local GPU embedding):

| Stage | Time |
|---|---|
| query embedding | ~0.15 s |
| vector search | ~0.33 s |
| re-validation (one Firestore `get` per record, sequential) | ~1.5 s |
| **model call** | **everything else** |

Facts established against OpenCode 1.17.11 with a fake provider (no credentials):

- OpenCode sends `reasoning: {effort: "medium", summary: "auto"}` to any `gpt-5*` model unless told
  otherwise. Nothing in this repo overrode it.
- `variant` in a message only works if the model defines `variants`; a model's `options.reasoningEffort`
  in the config also overrides the default.
- A warm OpenCode adds ~0.1 s per message. The first message after boot adds ~2.3 s, and `opencode serve`
  itself takes ~1.4 s to boot. The persistent ChatGPT worker pays this once; the API-key worker pays it on
  every request, on top of ~1.9 s of Docker setup.
- `GET /event` streams `message.part.delta` events as tokens are produced.

## What changed

| Change | Where | Effect |
|---|---|---|
| Per-stage timing log | `qa.Run`, `log_timing` | one `qa_timing` line per question |
| Reasoning effort per request | `qa.route`, workers | simple questions use `low`, others `medium` |
| Short answer budget, no `claim_id`/`support` in the schema | `INSTRUCTION`, `BUDGETS` | fewer output tokens |
| Unsupported claims are dropped, quotes repaired | `qa.parse_output`, `qa.locate_quote` | no second model call for a reworded quote |
| Web search only when needed | `qa.answer_events` | no web round trip when the KB has evidence |
| Parallel source fetch | `web_sources.gather` | N sources cost one fetch, not N |
| Batched Firestore reads, concurrent sibling queries | `evidence.ReadCache`, `build`, `expand` | ~24–48 reads become 3 batches |
| Duplicate work removed | `rag.prepare`, `OAuthAnswer` | scope resolved once, Docker asked once, credential saved only when it changed, no separate `export` exec |
| Audit row written in the background | `qa.record_run` | one transaction less on the critical path |
| Streaming over SSE | `POST /rag/ask/stream`, `ClaimStream` | sources at once, answer sentence by sentence |
| Answer cache | `qa_cache` | repeated questions skip the model |

The model the user selected is never replaced: the router only changes effort and answer length.

### Router

`qa.route` takes the deep path (`QA_DEEP_EFFORT`, more claims) when any of these holds: question longer than
280 characters, more than two sentence marks, confirmed user facts, a past as-of date, comparison words
(`so sánh`, `khác nhau`, `ngoại lệ`, …), more than three source documents, or web evidence. Everything else
takes the fast path. `QA_ROUTER_ENABLED=false` restores the previous behaviour (provider default effort).

Retrieval scores are **not** used: in the retrieval experiment the top score of a correct and of a wrong
retrieval overlap almost completely (median 0.49 vs 0.45), so a threshold would be noise.

### Claim validation without retries

Each claim is checked against the evidence pack as before. A claim that fails is dropped and the answer
keeps the rest, with the limitation code `unsupported_claims_removed`. A quote that is *almost* in the cited
source (similarity ≥ 0.85) is replaced by the real passage; an invented quote is still rejected. Only
structurally unusable output (no JSON, wrong schema, nothing supported) is retried, once, and only while
less than half of `QA_DEADLINE_SECONDS` is used.

### Web search

With `QA_WEB_PREFETCH=when_empty` (default) the web is searched before the model only if the knowledge base
returned nothing or `web_mode` is `examples`. Otherwise the model may still ask for it by answering
`insufficient_evidence` with `search_queries`, which triggers one follow-up search and one more call.
`always` restores the previous order.

### Cache

Key: policy version, knowledge bases **with their published generation**, as-of date, normalised question
(case, accents, punctuation), retrieval mode, web mode, `top_k`, provider and model. Publishing a corpus
changes the generation, so old entries become unreachable. Before a cached answer is returned, every
provision it was built from is re-read and must still be alive and applicable; otherwise the entry is
dropped. Not cached: questions with `session_facts`, answers that used the web, answers produced while
anything degraded (`source_limitations` notes such as `embedding_unavailable`), and non-`answered` results.
The cache is per process (`QA_CACHE_TTL_SECONDS`, `QA_CACHE_MAX_ENTRIES`).

## Streaming protocol

`POST /api/v1/rag/ask/stream` takes the same body as `/rag/ask` and requires the same session. Failures before
the answer starts (access, credentials, scope) are ordinary HTTP errors. After that the response is
`text/event-stream`:

| Event | Payload | Meaning |
|---|---|---|
| `stage` | `stage`: `retrieving`, `web`, `drafting` (+`tier`), `cached` | progress |
| `sources` | `items[]`: title, article, clause, source_type, source_url, evidence_url, quote | evidence found, before the model runs |
| `claim` | `text` (with `[n]` markers), `citations[]` | one answer sentence that already passed validation |
| `reset` | – | discard the claims shown so far (retry or follow-up search) |
| `done` | `response`: the complete `AskResponse` | authoritative; replaces everything streamed |
| `error` | `code`, `message`, `status` | failure after the stream started |

A claim is shown only after it passes the same checks as in the final answer. The one check that needs the
whole output (an inference needs `assumptions`) is applied to streamed claims too, using the assumptions
already written; the model is asked to write them first. The `done` event is always the truth.

The UI falls back to `POST /rag/ask` when the stream endpoint answers 404 or 405, so a newer UI works with
an older backend.

### Proxies

`nginx` (`infra/nginx/api.conf`) has a dedicated location with `proxy_buffering off`. The app also sends
`X-Accel-Buffering: no`. If answers only appear all at once behind a tunnel or CDN, that hop is buffering:
look at the `stage`/`sources` timing in the browser's network panel.

## Reading the timing log

```json
{"event": "qa_timing", "requestId": "…", "status": "answered", "tier": "fast", "cache": "miss",
 "totalMs": 6816, "stagesMs": {"scope": 0, "cache": 0, "embed": 150, "search": 330, "validate": 90,
 "expand": 60, "llm": 5900}, "evidenceItems": 5, "llmCalls": 1, "claimsDropped": 1, "quotesRepaired": 0}
```

`web`/`web2` appear when the web ran. The same fields (`latencyMs`, `tier`, `cacheHit`) are stored on the
`evidence_runs` row. The line holds no question or answer text.

## Configuration

See `QA_*` in `apps/api/.env.example`.

## Verifying

- `pytest` – unit and flow tests (`test_qa_latency.py`, `test_streaming.py`, `test_claim_stream.py`).
- `node --test "apps/web/tests/*.test.mjs"` – the browser-side SSE reader.
- `scripts/opencode_poc/verify-effort-stream.sh` – runs the real OpenCode worker in Docker against a fake
  provider and shows the effort it sent and the streamed deltas.

## Not done

- API-key workers still start a Docker network, two containers and an OpenCode server for every request
  (about 5–8 s before the model starts). This isolation is deliberate; changing it is a security decision.
- Effort `low` trades some reasoning for speed. Run `scripts/evaluate_legal_qa.py` before and after, or set
  `QA_FAST_EFFORT=medium`, if answer quality on your questions drops.
