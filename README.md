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
  - [5. Start Frontend Web (Next.js)](#5-start-frontend-web-nextjs)
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
│   ├── web/                     # Next.js 14+ frontend application (TypeScript, App Router)
│   └── api/                     # FastAPI backend service (Python 3.11+, SQLAlchemy, pgvector)
├── packages/
│   └── ui/                      # Shared reusable UI component library & design tokens
├── infra/
│   ├── docker/                  # Docker Compose and service definitions (PostgreSQL, Redis)
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
| `apps/web/` | Web Client | Next.js, React, TypeScript | @minhnm162, @teddywristh | Search interfaces, document viewer, chat UI, responsive layouts |
| `apps/api/` | Backend & AI Services | FastAPI, Python, SQLAlchemy | @MinhQuangQu, @teddywristh | REST API, database access, vector search, LLM orchestration |
| `packages/ui/` | Shared UI Library | React, CSS Tokens | @minhnm162, @teddywristh | Reusable design components, badges, modals, typography |
| `infra/` | Infrastructure | Docker Compose, PostgreSQL, Redis | @teddywristh, @MinhQuangQu | Database provisioning, vector storage, caching layer |
| `docs/` | Project Docs | Markdown | @teddywristh, @leducminh290506-eng | Architecture, setup guides, conventions, testing strategy |
| `scripts/` | Tooling & Utilities | Python / Shell | @teddywristh, @leducminh290506-eng | Setup automation, preflight checks, database seeding |
| `.github/` | Workflows & CI/CD | GitHub Actions YAML | @teddywristh | Automated testing, linting, code quality gates |

---

## Prerequisites

Before starting local development, ensure your machine has:
- **Git** (2.30+)
- **Node.js** (v20 LTS recommended) & **npm**
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
cp .env.example .env

# Web frontend
cp apps/web/.env.example apps/web/.env.local

# API backend
cp apps/api/.env.example apps/api/.env

# Infrastructure
cp infra/.env.example infra/.env
```

### 3. Start Infrastructure (Docker)
Start PostgreSQL (with `pgvector`) and Redis:
```bash
docker compose -f infra/docker/docker-compose.yml up -d
docker compose -f infra/docker/docker-compose.yml ps
```

### 4. Start Backend API (FastAPI)
```bash
cd apps/api
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- API Health Check: `http://localhost:8000/api/v1/health`
- Interactive Swagger Docs: `http://localhost:8000/docs`

### 5. Start Frontend Web (Next.js)
```bash
cd apps/web
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## Repository Conventions

For detailed guidelines, see [docs/conventions.md](file:///c:/Users/DELL/G1_Web_Design/docs/conventions.md).

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
- **Editor Configuration**: Consistently enforced by [`.editorconfig`](file:///c:/Users/DELL/G1_Web_Design/.editorconfig).
- **Backend Linting**: `ruff check .` and `ruff format .`
- **Frontend Linting**: `npm run lint` and TypeScript compilation `tsc --noEmit`.
- **Automated CI**: GitHub Actions validates linting, type-checking, and test suites on all PRs.

---

## Documentation & Backlog Roadmap

| Phase / Issue | Description | Status |
| :--- | :--- | :--- |
| **Issue #1 (#5)** | **Initialize monorepo structure and repository conventions** | **Completed** |
| Issue #2 (#6) | Scaffold Next.js frontend and shared UI components | Planned |
| Issue #3 (#7) | Scaffold FastAPI backend and health endpoint | Planned |
| Issue #4 (#8) | Configure PostgreSQL, pgvector and Redis via Docker Compose | Planned |
| Issue #5 (#9) | Add Alembic migrations, environment config, and seed workflow | Planned |
| Issue #6 (#10) | Add lint, tests, and GitHub Actions CI matrix | Planned |
| Issue #7 (#11) | Write architecture and local setup documentation | Planned |
| Issue #12 | Define test strategy and quality gates | Planned |
| Issue #13 | Add local environment preflight and setup validation | Planned |

---

## Responsible AI & Disclaimer

**Legal AI Assistant** is an information retrieval, research, and analysis support platform.
- It uses artificial intelligence to discover, summarize, explain, and compare legal provisions.
- AI-generated responses should **never** be considered formal legal advice or an official interpretation of Vietnamese law.
- For legally binding decisions, users must verify all claims against the original legal texts (provided directly via source citations) and consult certified legal professionals.
