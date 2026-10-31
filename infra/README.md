# Infrastructure

Current backend MVP: Firebase Authentication, Firestore and private Firebase Storage, with FastAPI behind an Nginx gateway. No PostgreSQL or Redis is required.

- `docker/Dockerfile.api`: non-root backend image.
- `docker/docker-compose.yml`: local backend and gateway, port 8001.
- `nginx/api.conf`: per-IP rate/connection limits, body limits and structured access logs.
- `firebase/firestore.rules`, `firebase/storage.rules`: deny client access; backend enforces permissions.
- `firebase/firestore.indexes.json`: supported backend queries plus existing historical indexes.
- Root `firebase.json`: loopback emulators; `firebase.docker.json`: explicit all-interface local Docker variant.

Follow [backend operations](../docs/backend-operations.md) for commands, network binding, IAM, dev/prod separation, deployment and recovery. Emulators are separate from Docker Compose and must start first. Never use the Docker emulator configuration in production.
