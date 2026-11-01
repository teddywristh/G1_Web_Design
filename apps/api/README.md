# `apps/api` — FastAPI Backend & AI Services

## Overview
`apps/api` is the backend REST API service powering the **Legal AI Assistant** platform. It handles legal document ingestion, full-text and vector search, conversational AI research workflows, citation retrieval, and user authentication.

## Tech Stack
- **Framework**: FastAPI (Python 3.11+)
- **Data access**: Firebase Admin SDK repositories
- **Data services**: Cloud Firestore + Firebase Storage
- **AI / Search**: OpenAI / Anthropic / Cohere / HuggingFace embedding & LLM APIs
- **Validation**: Pydantic v2
- **Testing & Code Quality**: Pytest, HTTPX, Ruff

## Directory Structure (Planned in Issue #3 & #7)
```
apps/api/
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
│   ├── repositories/       # Firestore access boundary
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
- Firestore schema and repository workflows.
- Firebase Authentication token verification and authorization.
- Firebase Storage PDF lifecycle and API security.
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
Run the development server with hot-reload:
```bash
uvicorn app.main:app --reload --port 8000
```
API Documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## RAG pipeline

The RAG backend reads prepared legal chunks from the Firestore
`document_chunks` collection. It does not read PDF files during question
answering.

- `POST /api/v1/rag/ask`: send `{"question": "...", "top_k": 5}`. The service
  embeds the Vietnamese question, ranks stored chunks by vector similarity and
  simple keyword overlap, and asks the LLM to answer only from those chunks.
- `apps/api/app/core/database.py` is the single database connection entry point.
  It reuses the Firebase Admin connection and returns the Firestore client.

Each chunk should contain `content` (or `text`), `embedding`, `document_id`,
`document_title`, and optional legal metadata such as `article`, `clause`,
`point`, `page_number`, and `source_url`. Set `OPENAI_API_KEY` in
`apps/api/.env` to enable question embedding and answering. Firestore
credentials and emulator settings are documented in the repository Firebase
setup guide.
