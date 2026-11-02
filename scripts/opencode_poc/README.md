# OpenCode isolated-worker PoC

This is a local, synthetic test, not an application backend or a production worker. It runs OpenCode 1.17.11 with fake per-worker credentials and an in-container OpenAI Responses stub; it never calls a model or uses a real API key. It requires Docker and a local OpenCode 1.17.11 binary. By default it uses the local image `legal-api-backend:verify`; create a compatible image from `infra/docker/Dockerfile.api` if needed, or set `OPENCODE_POC_IMAGE` to an existing Python image. Set `OPENCODE_POC_BINARY` if OpenCode is not on PATH.

```bash
scripts/opencode_poc/run.sh
```

Two containers run concurrently. Each uses a different fake credential, an empty workspace, non-root UID, `--network none`, read-only root filesystem, dropped capabilities, `no-new-privileges`, and bounded memory/processes. A fake provider returns a valid response, and the probe checks that each OpenCode process sent only its own fake key and advertised no tools. Two further workers receive fabricated `bash` and `read` tool calls; the probe checks that a file cannot be created, a canary file does not leak to the fake provider, and session abort stops subsequent provider requests. A mock local budget proxy forwards at most three provider requests and rejects subsequent requests; this proxy shares the test container and is not an independent security boundary. Temporary files disappear when the containers stop.

The version check is a compatibility check, not binary provenance verification. Pin the image by digest and verify the OpenCode artifact separately before any deployment. `--network none` prevents real provider access; a production implementation still needs an independently enforced, tested egress allowlist, per-request/session isolation, request and spend limits, bounded worker startup and teardown, error redaction, and repeatable integration and performance tests. A model-provider access token must never be supplied to this PoC.

A second proof separates the synthetic gateway from the worker:

```bash
scripts/opencode_poc/run-private.sh
```

It creates two temporary internal Docker networks, a dedicated fake gateway for each, and workers that attempt to connect to the other user's gateway, a metadata address and a public IP. Both workers then send prompts through their own gateway; a third trial tests a malicious shell tool response against the gateway's three-request ceiling. All containers and networks are removed afterwards. The gateway is attached to Docker's bridge but returns synthetic responses and does **not** forward to real providers. This proves only the tested network topology; production still needs verified HTTPS-only allowlisted egress, identity binding, durable lifecycle controls, real provider integration and load testing.
