# Deployment

The current backend deployment and recovery instructions are maintained in
[backend-operations.md](backend-operations.md). Local setup and verification are
in [apps/api/README.md](../apps/api/README.md).

Backend: FastAPI container + Firebase Auth/Firestore/Storage, behind a gateway
with TLS and shared rate limits. Local Docker Compose includes Nginx. Cloud
resources and production deployment are operator actions; tests use emulators.

Frontend deployment remains separate from backend. No AI service deployment is
required for the implemented backend MVP.
