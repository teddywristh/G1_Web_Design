# Local Nemotron embedding endpoint

Independent of Firebase, RAG, PDF ingestion and the backend API. Weights are read
locally; the service never downloads weights or switches models automatically.
Runtime follows the [NVIDIA model card](https://huggingface.co/nvidia/Nemotron-3.5-Embed-1B-BF16).

## Install and run

From the repository root (Python 3.12):

```bash
python3.12 -m venv .venv-embed
.venv-embed/bin/python -m pip install torch
.venv-embed/bin/python -m pip install -r apps/embedding/requirements.txt
bash scripts/embedding-host.sh
```

Select the CUDA wheel matching your driver using https://pytorch.org/get-started/locally/.
If using an existing environment, set `EMBEDDING_PYTHON=/absolute/path/to/python`.
The model is expected at `models/nemotron-3.5-embed-1b`; override with
`EMBEDDING_MODEL_PATH`. The example env file is documentation; export variables
in your shell before starting (the script does not automatically load .env).
One worker, one active inference, batch size 1; requests can contain up to 32 texts
processed sequentially. Inputs are truncated at 512 tokens by default.

```bash
curl --fail http://127.0.0.1:8010/ready
curl --fail http://127.0.0.1:8010/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"input":["Điều kiện chấm dứt hợp đồng lao động"],"input_type":"query","dimensions":1536}'
```

`input_type=passage` calls encode_document; query calls encode_query. Model prompts
are applied by Sentence Transformers. Prefix truncation is followed by L2
normalization. Default output is 1536 dimensions, allowed range 1–2048.
GET /health reports process health and model_loaded; GET /ready returns 503 until
loaded. Missing dependencies, CUDA or weights keep the process alive but unready.
429 means another inference is running; retry after 1 second. 503 also covers GPU
OOM and invalid model output. Logs contain timing/counts, never input content.

## Expose the port

Local endpoint: `http://127.0.0.1:8010/v1/embeddings`.
To make it reachable on your LAN:

```bash
export EMBEDDING_HOST=0.0.0.0
export EMBEDDING_API_KEY='replace-with-a-long-random-key'
bash scripts/embedding-host.sh
```

Call `http://<host-ip>:8010/v1/embeddings` with `Authorization: Bearer <key>`.
For Internet access terminate HTTPS with your own tunnel/reverse proxy to port
8010 and keep the API key enabled. No tunnel account/domain is configured here.
Use /ready to check actual availability; /health alone does not confirm inference.

## Tests

```bash
PYTHONPATH=apps/embedding .venv/bin/python -m pytest -c apps/embedding/pyproject.toml apps/embedding/tests -q
```

Tests inject deterministic model outputs and do not claim GPU validation.
The existing GPU smoke test at `smoke_test_embed.py` can be run with the inference
Python environment. Benchmark real GPU latency/VRAM before raising token limits.

## Integrated local application

The app at http://127.0.0.1:8085 uses backend port 8000, Firebase emulators
(Auth 9099, Firestore 8081, Storage 9198), the ingestion worker and GPU host 8010.
RAG/document handlers are restored for the full local application. Both ingestion
and query use `EMBEDDING_PROVIDER=local`, batch size 1 and all PDF chunks.
Provider keys are only needed for the answering LLM, not for embeddings.

Authenticated endpoint: `POST /api/v1/embeddings` on port 8000, with the browser
session cookie and CSRF header (or a valid Firebase bearer token). Body accepts
`input` and `input_type`; dimensions/model come from the server's configured
profile. Browser traffic never needs the private GPU host key.

After Firebase emulators and embedding host are ready, start missing services:

```bash
bash scripts/local-embed-demo.sh
```

The script preserves existing processes and stores new-process logs/PIDs under
`.data/local-demo/`. It uses the Python selected by `DEMO_PYTHON` (default `python`).
The existing backend at port 8000 runs with reload; saving code reloads it.

In the UI: sign in, create a private knowledge base, upload PDF, wait for Ready,
select that KB and hybrid retrieval in Q&A, then choose/configure the answering
provider or connect ChatGPT in Settings. ChatGPT sign-in supports hybrid retrieval
when local embedding is enabled. Google sign-in still requires its OAuth origin
configuration; external LLM availability is independent of local embedding.

A PDF indexed with an older profile shows a reindex action. Open it and click
process again. Multi-document KBs with an existing incompatible generation need
a complete KB migration before publishing; the service rejects mixed profiles.
For immediate local tests, create a fresh private KB. No existing corpus was
rewritten automatically.

Real smoke test completed: authenticated embedding, PDF upload, GPU ingestion,
Firestore generation publication, vector search (2 hits), PDF download and deletion
of the synthetic test PDF. LLM calls were not made with user credentials.
Cloud Hosting/deployment remains deferred in favor of the requested local test.

## Verified on this machine (2026-11-03)

Existing inference Python: `/home/minhquang/miniconda3/envs/embed/bin/python`.
RTX 3050 6 GB, PyTorch 2.8.0+cu126. CUDA is accessible outside the execution
sandbox. Model loaded successfully with BF16 + SDPA. Real Vietnamese query and
passage requests returned finite 1536-dimensional vectors with norms
1.000000025 and 1.000000011. First query including warm-up took 65.147 seconds;
subsequent passage took 0.421 seconds. These are smoke measurements, not a
throughput or long-duration stability benchmark.

Reproduce:

```bash
EMBEDDING_PYTHON=/home/minhquang/miniconda3/envs/embed/bin/python bash scripts/embedding-host.sh
python apps/embedding/smoke_client.py
```

Contract tests: 3 passed. The integrated backend restores RAG/document routes for local application testing.
Warm repeat: query 0.278 seconds, passage 0.041 seconds (single short text).
