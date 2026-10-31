# System Architecture & Directory Responsibilities

## Overview
**Legal AI Assistant** is a modern legal search, analysis, and verification platform designed specifically for Vietnamese legal documents.

> MVP infrastructure decision: Firebase Authentication, Cloud Firestore and
> Firebase Storage are the source of truth for identity, metadata and files.
> The PostgreSQL/Redis diagram below is a future-scale option, not part of the
> Firebase-first MVP described in `docs/plans.md`.

The architecture emphasizes:
1. **Source Transparency**: Every AI generated response is grounded in traceable legal provisions (Articles, Clauses, Decrees).
2. **Speed & Scalability**: Fast hybrid search (relational + pgvector embedding similarity) with Redis caching.
3. **Modularity**: Clean monorepo boundaries between the Next.js frontend, FastAPI backend, shared UI packages, and Docker infrastructure.

---

## 1. High-Level Architecture Diagram

```
+--------------------------------------------------------------------------+
|                              Client Browser                              |
|                   (Desktop / Tablet / Mobile Viewports)                  |
+--------------------------------------------------------------------------+
                                     │
                                     │ HTTP / HTTPS (REST API)
                                     ▼
+--------------------------------------------------------------------------+
|                     Next.js Frontend (apps/web)                          |
|             React Server Components + Client Interactions                |
+--------------------------------------------------------------------------+
                                     │
                                     │ REST JSON (/api/v1/*)
                                     ▼
+--------------------------------------------------------------------------+
|                       FastAPI Backend (apps/api)                         |
|              Request Validation (Pydantic), Auth, Routing                |
+────────────────────────────────────┬─────────────────────────────────────+
                  │                  │                   │
                  ▼                  ▼                   ▼
    +────────────────────────+ +──────────────+ +──────────────────────────+
    | PostgreSQL + pgvector  | | Redis Cache  | | External LLM & Embedding |
    | (Relational + Vectors) | | (Sessions,   | | (OpenAI / Anthropic /    |
    |  Legal Docs & Chunks   | |  Queries)    | |  Cohere APIs)            |
    +────────────────────────+ +──────────────+ +──────────────────────────+
```

---

## 2. Directory Responsibilities & Ownership Matrix

| Directory | Primary Scope | Lead Assignees | Key Responsibilities |
| :--- | :--- | :--- | :--- |
| `apps/web` | Next.js Frontend App | @minhnm162, @teddywristh | UI views, search interactions, citation inspector, responsive design |
| `apps/api` | FastAPI Backend | @MinhQuangQu, @teddywristh | REST API endpoints, legal ingestion, vector search, LLM orchestration |
| `packages/ui` | Shared UI Library | @minhnm162, @teddywristh | Reusable buttons, badges, modals, design tokens, legal status pills |
| `infra` | Infrastructure & Docker | @teddywristh, @MinhQuangQu | Docker Compose (PostgreSQL, pgvector, Redis), container builds |
| `docs` | Documentation | @teddywristh, @leducminh290506-eng | Architecture, local setup, testing strategy, development conventions |
| `scripts` | Development Automation | @teddywristh, @leducminh290506-eng | Environment preflight checks, database seeding, migration shortcuts |
| `.github` | CI/CD & Repository | @teddywristh | GitHub Actions workflows, issue templates, PR review gates |

---

## 3. Core User Journey Data Flow

```
[User Question]
       │
       ▼
1. Ask / Search (apps/web)
       │
       ▼
2. API Router & Query Embedding (apps/api)
       │
       ├──────────────► Hybrid Search in PostgreSQL (Full-text + pgvector)
       │                                  │
       ▼                                  ▼
3. Top Relevant Articles & Clauses Retrieved
       │
       ▼
4. Context Ingestion & Prompt Synthesis
       │
       ├──────────────► LLM Generation with Strict Citation Constraints
       │                                  │
       ▼                                  ▼
5. AI Response + Traceable Citations Sent to Frontend
       │
       ▼
6. Verify (apps/web)
   User inspects original legal provisions, checks validity date & amendments
```

---

## 4. Environment Configuration Isolation
Each component manages its own configuration through environment variables:
- **`apps/web/.env.example`**: Defines client-side variables (`NEXT_PUBLIC_*`).
- **`apps/api/.env.example`**: Defines backend secrets, database connection string, and external API keys.
- **`infra/.env.example`**: Defines container service ports and database credentials for Docker Compose.

**Security Rule:** Never commit `.env` or `.env.local` files to version control. Only `.env.example` with non-secret defaults should ever be committed.
