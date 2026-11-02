# Legal AI Assistant (Trợ Lý Pháp Lý AI)

> An intelligent legal search, analysis, and verification platform designed to make Vietnamese legal information accessible, understandable, and verifiable.

---

## Table of Contents
- [Overview & Vision](#overview--vision)
- [Core User Journey: Ask → Search → Understand → Verify](#core-user-journey-ask--search--understand--verify)
- [Monorepo Directory Structure](#monorepo-directory-structure)
- [Directory Ownership & Responsibilities](#directory-ownership--responsibilities)
- [Prerequisites](#prerequisites)
- [Quickstart & Local Development](#quickstart--local-development)
  - [1. Clone & Branch](#1-clone--branch)
  - [2. Environment Configuration](#2-environment-configuration)
  - [3. Start Infrastructure (Docker)](#3-start-infrastructure-docker)
  - [4. Start Backend API (FastAPI)](#4-start-backend-api-fastapi)
  - [5. Start the Ingestion Worker](#5-start-the-ingestion-worker)
  - [6. Start Frontend Web (static HTML)](#6-start-frontend-web-static-html)
- [Repository Conventions](#repository-conventions)
  - [Branch Naming](#branch-naming)
  - [Commit Messages (Conventional Commits)](#commit-messages-conventional-commits)
  - [Pull Request Process](#pull-request-process)
- [Code Quality & Linting](#code-quality--linting)
- [Documentation & Backlog Roadmap](#documentation--backlog-roadmap)
- [Responsible AI & Disclaimer](#responsible-ai--disclaimer)

---

## Overview & Vision

Vietnamese law is distributed across an extensive and continuously evolving collection of laws, codes, decrees, circulars, resolutions, decisions, and consolidated documents. For individuals and businesses, finding the right regulation, checking whether it remains in legal effect, interpreting technical language, and discovering amended provisions is challenging and time-consuming.

**Legal AI Assistant** solves this problem by uniting:
1. **Intelligent Legal Search**: Full-text keyword and semantic vector search across laws, articles, and clauses.
2. **Structured Legal Knowledge Base**: Clear legal hierarchies with status indicators (Effective, Amended, Expired).
3. **Conversational AI Assistance**: Natural language explanations and synthesis grounded in traceable legal provisions.
4. **Source Verification**: Direct citations linking AI responses to original Articles and Clauses.

---

## Core User Journey: Ask → Search → Understand → Verify

```text
       ┌──────────┐
       │   ASK    │  Describe a real-world legal situation in natural language.
       └────┬─────┘
            ▼
       ┌──────────┐
       │  SEARCH  │  Find relevant legal instruments, Articles, and Clauses.
       └────┬─────┘
            ▼
       ┌──────────┐
       │UNDERSTAND│  Read AI-assisted summaries with clear legal explanations.
       └────┬─────┘
            ▼
       ┌──────────┐
       │  VERIFY  │  Inspect official citations and confirm document legal status.
       └──────────┘
```

---

## Monorepo Directory Structure

The project is structured as a modular monorepo:

```text
G1_Web_Design/
├── apps/
│   ├── web/                     # Plain HTML/CSS/JavaScript frontend (no build step; legacy Next.js in src/)
│   └── api/                     # FastAPI backend service (Python 3.11+, Firebase Admin SDK)
├── packages/
│   └── ui/                      # Shared reusable UI component library & design tokens
├── infra/
│   ├── docker/                  # Docker API/gateway, Firebase rules and indexes
│   ├── .env.example             # Infrastructure environment template
│   └── README.md                # Infrastructure documentation
├── docs/
│   ├── architecture.md          # System architecture, data flow & component design
│   ├── conventions.md           # Branching, Conventional Commits, PR standards
│   └── README.md                # Documentation catalog
├── scripts/                     # Cross-cutting development & preflight utilities
├── .github/
│   ├── ISSUE_TEMPLATE/          # Standardized issue templates (bug, feature, task)
│   ├── pull_request_template.md # Pull request review template
│   ├── CODEOWNERS               # Directory ownership & automatic review assignment
│   └── workflows/               # GitHub Actions CI/CD workflows
├── .editorconfig                # Universal indentation and formatting rules
├── .env.example                 # Root environment template
├── .gitignore                   # Comprehensive ignores (Python, Node.js, IDEs, secrets)
└── README.md                    # Project overview and development guide
```

---

## Directory Ownership & Responsibilities

| Path | Primary Component | Tech Stack | Lead Assignees | Responsibilities |
| :--- | :--- | :--- | :--- | :--- |
| `apps/web/` | Web Client | HTML, CSS, JavaScript | @minhnm162, @teddywristh | Search interfaces, document viewer, chat UI, responsive layouts |
| `apps/api/` | Backend & AI Services | FastAPI, Python, Firebase | @MinhQuangQu, @teddywristh | REST API, database access, vector search, LLM orchestration |
| `packages/ui/` | Shared UI Library | React, CSS Tokens | @minhnm162, @teddywristh | Reusable design components, badges, modals, typography |
| `infra/` | Infrastructure | Docker, Firebase Emulator, Nginx | @teddywristh, @MinhQuangQu | Firebase setup, private file storage, API gateway |
| `docs/` | Project Docs | Markdown | @teddywristh, @leducminh290506-eng | Architecture, setup guides, conventions, testing strategy |
| `scripts/` | Tooling & Utilities | Python / Shell | @teddywristh, @leducminh290506-eng | Setup automation, preflight checks, database seeding |
| `.github/` | Workflows & CI/CD | GitHub Actions YAML | @teddywristh | Automated testing, linting, code quality gates |

---

## Prerequisites

Before starting local development, ensure your machine has:
- **Git** (2.30+)
- **Node.js** (v22+) & **npm** (only for `firebase-tools`; the web app needs no npm)
- **Java** (21+, for Firebase Emulator)
- **Python** (3.11+ recommended) & `venv` / `pip`
- **Docker Desktop** or **Docker Engine** with Docker Compose v2+

---

## Quickstart & Local Development

### 1. Clone & Branch
```bash
git clone https://github.com/teddywristh/G1_Web_Design.git
cd G1_Web_Design
git checkout -b feat/your-feature-name
```

### 2. Environment Configuration
Copy `.env.example` templates to your local configuration files. **Never commit `.env` files to git.**
```bash
# Root environment (optional central reference)
test -e .env || cp .env.example .env

# API backend
test -e apps/api/.env || cp apps/api/.env.example apps/api/.env

# Infrastructure
test -e infra/.env || cp infra/.env.example infra/.env
```

### 3. Start Infrastructure (Docker)
The backend MVP uses Firebase Emulator Suite for local development:
```bash
npm install -g firebase-tools@15.12.0
firebase emulators:start --project demo-legal-api --only auth,firestore,storage
```
Use `apps/api/.env.example` for matching demo configuration (the commands above preserve an existing `apps/api/.env`; check that it points to the emulator and that `BACKEND_CORS_ORIGINS` includes `http://127.0.0.1:8085`). Against a real Firebase project, deploy the indexes first: `firebase deploy --only firestore:indexes --project <id>` (the worker and vector search need them). For Docker API/gateway,
follow [the operations runbook](docs/backend-operations.md), including the separate
Docker emulator binding configuration.

Run Firebase CLI commands from the repository root, where `firebase.json` lives. On a shared
project, review the index changes and any deletion prompts before deploying. Wait for indexes to
reach **Ready**; the emulator does not enforce the same composite and vector indexes as Firestore.
For an existing cloud configuration, do not overwrite `apps/api/.env` with the emulator template.

### 4. Start Backend API (FastAPI)
```bash
cd apps/api
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```
Run these from `apps/api` with the emulators from step 3 already running.
- API Health Check: `http://localhost:8000/health`
- Interactive Swagger Docs: `http://localhost:8000/docs`

### 5. Start the Ingestion Worker
Uploaded PDFs are parsed, embedded and indexed by a separate process. In a third terminal, with the same virtualenv:
```bash
cd apps/api
python -m app.workers.ingestion
```
Without it, documents stay `queued`. Embedding needs an OpenAI key (personal key in Settings, or a shared key set by an admin). See [docs/knowledge-rag.md](docs/knowledge-rag.md).

### 6. Start Frontend Web (static HTML)
The web app is plain HTML, CSS and JavaScript. There is nothing to install or build. From the repository root:
```bash
python -m http.server 8085 --bind 127.0.0.1 --directory apps/web
```
Open `http://127.0.0.1:8085` (use `127.0.0.1`, not `localhost`, so the session cookie reaches the API). The backend allows ports 3000 and 8085 by default (`BACKEND_CORS_ORIGINS`). Change the API address in `<meta name="api-base">` of `apps/web/index.html`. See [apps/web/README.md](apps/web/README.md).

If the terminal is already in `apps/web`, run this instead:

```bash
python -m http.server 8085 --bind 127.0.0.1
```

The `--directory apps/web` argument is relative to the current directory; using it from inside
`apps/web` points to a nonexistent nested directory and returns 404. Stop the old server with
`Ctrl+C` before restarting on the same port. A `favicon.ico` 404 does not prevent the page loading.

The earlier Next.js app is still in `apps/web/src/` for reference and is not used by this setup.

---

## Repository Conventions

For detailed guidelines, see [docs/conventions.md](docs/conventions.md).

### Branch Naming
- Features: `feat/<short-description>` (e.g., `feat/search-bar`)
- Bug fixes: `fix/<short-description>` (e.g., `fix/api-cors-origin`)
- Scaffolding & Maintenance: `chore/<short-description>` (e.g., `chore/initial-setup`)
- Documentation: `docs/<short-description>` (e.g., `docs/local-setup`)

### Commit Messages (Conventional Commits)
All commit messages must follow the Conventional Commits specification:
```text
<type>(<scope>): <description in imperative mood>

Examples:
feat(api): implement GET /api/v1/health endpoint
fix(web): resolve mobile viewport search bar alignment
chore(infra): add docker-compose for postgres and redis
docs(root): update architecture and setup documentation
```
**Allowed types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`.  
**Allowed scopes:** `web`, `api`, `ui`, `infra`, `docs`, `scripts`, `deps`, `root`.

### Pull Request Process
1. Create a descriptive PR against `main` using the pull request template.
2. Ensure linting and tests pass locally before opening the PR.
3. Link the corresponding GitHub issue (e.g., `Closes #5`).
4. Obtain approval from the designated component owner(s) listed in `.github/CODEOWNERS`.

---

## Code Quality & Linting
- **Editor Configuration**: Consistently enforced by [`.editorconfig`](.editorconfig).
- **Backend Linting**: `ruff check .` and `ruff format .`
- **Frontend**: no build or lint step; `node --check apps/web/script.js apps/web/api.js` catches syntax errors.
- **Automated CI**: GitHub Actions validates linting, type-checking, and test suites on all PRs.

---

## Documentation & Backlog Roadmap

Backend implementation scope follows [backend-plan.md](docs/backend-plan.md),
not the scope or progress of historical issues. The current backend includes
Firebase authentication/profile/roles, document metadata and private PDF lifecycle,
metadata lookup with cursor pagination, admin user controls, atomic audit logs,
reconciliation, gateway limits and CI tests. It also provides private knowledge bases, a durable
ingestion worker and a cited legal Q&A workflow ([knowledge-rag.md](docs/knowledge-rag.md)).

See [knowledge bases & Q&A](docs/knowledge-rag.md), [API contract](docs/api-contract.md), [backend quickstart](apps/api/README.md),
[architecture](docs/architecture.md) and [operations](docs/backend-operations.md).

---

## Responsible AI & Disclaimer

**Legal AI Assistant** is an information retrieval, research, and analysis support platform.
- It uses artificial intelligence to discover, summarize, explain, and compare legal provisions.
- AI-generated responses should **never** be considered formal legal advice or an official interpretation of Vietnamese law.
- For legally binding decisions, users must verify all claims against the original legal texts (provided directly via source citations) and consult certified legal professionals.
