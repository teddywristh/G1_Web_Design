# Firebase Hosting demo

Firebase project identified in the existing cloud configuration: `legal-ai-dev-aeb51`.
The current API environment uses Firebase emulators; those data are separate from Firebase Cloud.

The Hosting build contains the frontend entry point and its HTML, CSS and JavaScript modules. Once the backend is
running securely on a public HTTPS origin, prepare and deploy it with:

```sh
python scripts/build-firebase-hosting.py --api-url https://YOUR-API-HOSTNAME
firebase deploy --only hosting --project legal-ai-dev-aeb51
```

The API hostname must point through a tunnel to FastAPI on `127.0.0.1:8000`.
Keep the embedding service on `127.0.0.1:8010` without a public route. The API
and ingestion worker must use Firebase Cloud credentials, with all emulator host
variables removed. Set `STORAGE_BACKEND=local` and `LOCAL_STORAGE_DIR` to an
absolute private directory on the host to keep PDFs and ingestion artifacts on
disk without a Cloud Storage bucket. Back up this directory separately: Firestore
does not contain the files, and both processes must use the same directory.
Configure the exact Hosting
origin in `BACKEND_CORS_ORIGINS` and enable secure cookies.

For `web.app` and a separate tunnel hostname, cookies are cross-site. This
requires `AUTH_COOKIE_SAMESITE=none` and `AUTH_COOKIE_SECURE=true`, but browsers
that block third-party cookies can still reject the session. Verify login and
refresh in the target browser before relying on this setup. A custom domain with
the app and API on the same site or a properly designed same-origin backend
proxy avoids that dependency.

Quick Tunnel hostnames change when restarted: rebuild and redeploy Hosting
after each change. Do not publish the site until authentication, registration,
resource limits and all publicly reachable endpoints have been reviewed and
the cloud dependencies and an answer-generation provider are configured.

After a restart, start the embedding host using the existing `embed` conda
environment, then run `bash scripts/start-cloud-demo.sh` from the repository
root. Run `bash scripts/publish-quick-tunnel.sh` once the tunnel connects; it
reads the new URL from the tunnel log, updates the GitHub Actions variable
`PUBLIC_API_URL`, and updates Hosting. It requires an authenticated GitHub CLI
with permission to update repository variables. The script records its process IDs in `.data/cloud-demo`; do not
terminate unrelated processes listening on these ports.

## GitHub Actions deployment

`.github/workflows/firebase-hosting.yml` verifies frontend assets on pull requests
and on every push to `main`; pushes to `main` deploy Hosting after verification.
The `PUBLIC_API_URL` variable is public configuration, not an API credential.
The deployment uses GitHub OIDC and a Firebase Hosting-only service account via
Workload Identity Federation, without a service account private key. The provider
is restricted to this repository's immutable ID and the `main` ref. The Google
Cloud provider and service account identifiers are stored in the GitHub variables
`FIREBASE_WIF_PROVIDER` and `FIREBASE_DEPLOY_SERVICE_ACCOUNT`.

Only `dist/hosting` is deployed; it contains the selected static frontend files.
Never put provider API keys, service-account credentials or `.env` files into
frontend assets, Actions variables, or the Hosting directory. The build checks
for common private-key patterns, but it is not a complete secret scanner.
CI deploys the frontend only. The backend, worker, local PDF storage and GPU
still require the host and Quick Tunnel to be running.

## AI connection persistence

Personal API keys and ChatGPT/OpenCode OAuth credentials are encrypted with
`AI_CREDENTIAL_ENCRYPTION_KEY` before being stored separately per user in
Firestore. Keep that key stable and back it up securely; changing or losing it
makes stored connections unreadable. Never expose it through the frontend or CI.
After a successful ChatGPT authorization, the backend saves the credential and
refreshes the encrypted copy after answers, allowing the single API process to
recreate its isolated worker after a restart. API and worker must keep using the
same Firebase project and encryption key. Multiple API processes/replicas are
not supported for OAuth refresh: they could race rotating credentials.

Disconnect removes the stored local credential; it does not confirm revocation
with OpenAI. Users may revoke the app in ChatGPT settings. A provider can still
expire or revoke a connection, in which case a new sign-in is required. If
Firestore is unavailable, existing credentials are retained and recovery is
retried later.
