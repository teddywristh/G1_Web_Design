# `infra/` — Infrastructure & Service Configurations

## Overview
`infra/` contains Docker Compose configurations, container specifications, and local/production infrastructure setup scripts for the **Legal AI Assistant** platform.

## Services Managed
1. **PostgreSQL 16 + pgvector**:
   - Stores legal document metadata, structured hierarchies (Laws, Articles, Clauses), and high-dimensional vector embeddings for similarity search.
   - Persistent volume mounted for local development.
2. **Redis 7**:
   - In-memory key-value store for caching legal search queries, user sessions, and rate-limiting counters.

## Directory Structure
```
infra/
├── docker/
│   ├── docker-compose.yml       # Local development multi-container orchestration (Issue #4)
│   └── Dockerfile.api           # Backend container definition
├── .env.example                 # Infrastructure environment variables
└── README.md
```

## Team Ownership & Responsibility
- **Primary Owner**: Infrastructure & DevOps Team (@teddywristh, @MinhQuangQu)
- **Responsibilities**:
  - Containerization and orchestration of PostgreSQL, pgvector, and Redis.
  - Ensuring persistent data volumes and reproducible environments.
  - Health check configurations for automated service readiness verification.
  - Production deployment manifests and environment configuration management.

## Starting Local Infrastructure (Issue #4)
```bash
docker compose -f infra/docker/docker-compose.yml up -d
docker compose -f infra/docker/docker-compose.yml ps
docker compose -f infra/docker/docker-compose.yml logs -f
```
To stop the services:
```bash
docker compose -f infra/docker/docker-compose.yml down
```
