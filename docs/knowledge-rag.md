# Knowledge bases, ingestion worker and legal Q&A

Implements `LegalAI_Implementation_Plan_VI_2026-11-03.md` for the backend (PR-00 to PR-06, PR-09 to PR-11).
The web UI (PR-07, PR-08) and server-side chat history are not part of this change.

## Flow

1. `POST /knowledge-bases` creates a private KB; `PUT .../documents/{id}/file` uploads a PDF through the
   existing lease/SHA-256 lifecycle. Completing the upload writes a `processing_jobs` row in the same
   transaction (outbox). Admin uploads to `legal_documents` do the same for the `shared` KB.
2. `python -m app.workers.ingestion` claims jobs with a lease and a fence counter. Stages are
   `parse` -> `embed` -> `publish`; only the lease holder can commit job state.
3. `publish` builds a complete new index generation (`search_chunks`), writes a manifest to Storage and moves
   `activeIndexGeneration` with a version check. Private KBs go live at once; the shared KB waits for
   `POST /admin/knowledge-bases/shared/publish` (also used to roll back to an earlier built generation).
4. `POST /rag/ask` runs `services/qa.py`: scope -> exact lookup + Firestore vector search -> canonical
   re-validation (tombstone, generation, legal time) -> sibling expansion -> LLM -> claim validation.

## Decisions (ADR summary)

| ADR | Decision |
|---|---|
| 01 | Canonical text lives in `provision_versions` and Storage; `search_chunks` is rebuildable |
| 02 | `legal_documents` stays shared and admin-owned; user files go to `knowledge_documents` |
| 03 | Jobs are Firestore rows with leases; a separate worker process runs them |
| 04 | Retrieval is Firestore vector + exact article/number lookup. There is no lexical (BM25) index |
| 05 | Backend runs a fixed workflow with budgets; the model never calls tools itself |
| 06 | Record `version` (If-Match) is separate from legal validity (`validFrom`, `endKind`, review state) |
| 07 | `EmbeddingProfile` (settings) is independent from the answering model; queries filter on its id |
| 08 | The model only returns server-issued evidence ids; citations are built by the backend |
| 09 | Web results are temporary evidence and are never written to a KB |
| 10 | No fallback to the old retriever: with `QA_WORKFLOW_ENABLED=false` `/rag/ask` returns 503 |

## Access matrix

| Resource | Owner | Other user | Admin |
|---|---|---|---|
| Private KB, documents, processing, evidence | read/write | 404 | 404 |
| Shared KB evidence | read | read | read, publish, review provisions |
| `/documents`, `/admin/documents` | n/a | read published | manage |

## Operating it

- Flags: `KNOWLEDGE_UPLOAD_ENABLED`, `QA_WORKFLOW_ENABLED`, `OFFICIAL_WEB_ENABLED`, `EXAMPLE_SEARCH_ENABLED`.
- Embeddings can use OpenAI or a separately configured OpenRouter system key. Set
  `EMBEDDING_PROVIDER=openrouter`, `OPENROUTER_EMBEDDING_MODEL` to the exact OpenRouter model ID,
  `OPENROUTER_EMBEDDING_API_KEY`, and `EMBEDDING_DIMENSIONS` to the model output size. The API
  and worker must use the same settings. The example free model
  `nvidia/nemotron-3.5-embed-1b:free` supports 1,536 dimensions, but NVIDIA prohibits confidential
  or personal data and logs usage for security and product improvement. The UI asks for explicit
  confirmation for each PDF and question; old jobs without confirmation are not sent. See the
  [provider terms](https://openrouter.ai/nvidia/nemotron-3.5-embed-1b:free).
- An OpenRouter embedding key is a **system-wide** credential, separate from the user's answering
  model/key. Embedding charges or rate limits apply to the system key; no paid-model fallback is
  performed. Use a secret manager in deployments and do not commit credentials.
- Changing the embedding provider, model or dimension changes the profile. Existing index
  generations must be rebuilt before hybrid search; the worker rejects publication that would
  mix different profiles. A changed dimension also needs a matching Firestore vector index.
- Required index: the vector index on `search_chunks` in `infra/firebase/firestore.indexes.json`
  (dimension must equal `EMBEDDING_DIMENSIONS`). The emulator does not run `find_nearest`; verify it on a
  real dev project.
- Job states: `needs_ocr` (scanned PDF, no OCR configured), `needs_configuration` (no usable key; retry via
  `.../reprocess`), `needs_review` (shared generation built, waiting for admin publish), `failed`.
- Maintenance: `python scripts/backend_admin.py --project P reconcile [--apply]` covers both document stores and
  chunks of generations that were never published. `python scripts/migrate_knowledge.py --project P [--apply]`
  queues existing admin PDFs and marks legacy `document_chunks` as quarantined.
- Rollback: publish an earlier built generation, or turn off `QA_WORKFLOW_ENABLED`.
- Evaluation: `python scripts/evaluate_legal_qa.py --manifest M --predictions P --split test` scores recorded
  responses (recall@k, status accuracy, citation resolvability, isolation leaks). It does not call paid APIs.

## Known limits

- Publishing copies the previous generation's chunks (write amplification); batch uploads when possible.
- Pages are physical PDF pages; printed page numbers are not extracted.
- Validity is only as good as the reviewed metadata. Shared documents take it from admin metadata; user files
  stay `validity_unverified`. Amendments are stored as `relationRefs` set by reviewers, never inferred.
- DNS is resolved before each fetch but the connection is not pinned to that address.
- The semantic claim check (LLM judge) and human review are not automated; the gold set and the vector-index
  spike on a real project still have to be produced by the team.
