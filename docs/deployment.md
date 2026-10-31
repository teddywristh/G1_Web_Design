# Deployment

Run `firebase emulators:start`, then from `apps/api` run
`uvicorn app.main:app --reload --port 8000`. Optional Docker startup:
`docker compose -f infra/docker/docker-compose.yml up --build`.

Deploy the frontend to Vercel and API to Cloud Run. Configure Firebase project
ID, Storage bucket and Application Default Credentials as platform secrets.
Deploy rules separately with Firebase CLI. Do not run ChromaDB on an ephemeral
container without persistent storage.
