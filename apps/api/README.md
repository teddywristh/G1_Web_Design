# `apps/api` — FastAPI Backend & AI Services

## Overview
`apps/api` is the backend REST API service powering the **Legal AI Assistant** platform. It handles legal document ingestion, full-text and vector search, conversational AI research workflows, citation retrieval, and user authentication.

## Tech Stack
- **Framework**: FastAPI (Python 3.11+)
- **ORM & DB Access**: SQLAlchemy 2.0 (Async) + Alembic migrations
- **Databases**:
  - **PostgreSQL + pgvector**: Relational legal metadata, document hierarchy, vector embeddings
  - **Redis**: Caching, session management, rate limiting
- **AI / Search**: OpenAI / Anthropic / Cohere / HuggingFace embedding & LLM APIs
- **Validation**: Pydantic v2
- **Testing & Code Quality**: Pytest, HTTPX, Ruff

## Directory Structure (Planned in Issue #3 & #7)
```
apps/api/
├── alembic/                # Database migrations
│   ├── versions/           # Migration revision files
│   └── env.py              # Alembic environment configuration
├── app/
│   ├── api/
│   │   └── v1/             # Versioned REST endpoints
│   │       ├── __init__.py
│   │       ├── health.py   # Health check endpoint
│   │       ├── search.py   # Legal search endpoints
│   │       └── chat.py     # AI interaction endpoints
│   ├── core/               # Application configuration & security
│   │   ├── config.py       # Pydantic Settings
│   │   └── security.py     # Auth & token utils
│   ├── db/                 # Database session and base models
│   │   ├── session.py      # Async SQLAlchemy session factory
│   │   └── redis.py        # Redis client pool
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic request/response schemas
│   ├── services/           # Business logic & AI orchestration
│   └── main.py             # FastAPI entrypoint
├── tests/                  # Automated tests (pytest)
│   ├── conftest.py
│   └── test_health.py
├── .env.example            # Environment variables template
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Ruff and tool settings
└── README.md
```

## Team Ownership & Responsibility
- **Primary Owner**: Backend & AI Team (@MinhQuangQu, @teddywristh)
- **Responsibilities**:
  - API architecture, routing, error handling, and request validation.
  - PostgreSQL schema design and Alembic migration workflows.
  - pgvector semantic search and ranking pipeline.
  - LLM prompt engineering, source citation retrieval, and RAG verification.
  - Performance, caching with Redis, and API security.

## Getting Started
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Activate your virtual environment and install requirements:
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```
Run the development server with hot-reload (scaffolded in Issue #3):
```bash
uvicorn app.main:app --reload --port 8000
```
API Documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
