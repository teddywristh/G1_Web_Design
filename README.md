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
  - [3. Start Firebase Emulator](#3-start-firebase-emulator)
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
1. **Legal Search**: Structured lookup by document number/article and semantic vector search when the embedding service and index are ready.
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
│   ├── web/                     # index.html + html/, css/, js/; no frontend build
│   ├── embedding/               # Optional local Nemotron embedding service
│   └── api/                     # FastAPI backend service (Python 3.11+, Firebase Admin SDK)
├── packages/
│   └── ui/                      # React components retained for the legacy frontend
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

- **Xem giao diện:** Python 3 và trình duyệt hiện đại. Frontend HTML/CSS/JS không cần cài npm hoặc build.
- **Chạy đầy đủ local:** Python 3.11+, Node.js 22+, Firebase CLI và Java 21+ cho emulator.
- **Embedding local:** môi trường Python riêng, model weights và GPU/CUDA theo [hướng dẫn embedding](apps/embedding/README.md). Không cần phần này nếu chỉ xem giao diện hoặc dùng provider embedding khác.
- **Docker:** dùng khi chạy API/gateway bằng container hoặc OpenCode local; không bắt buộc để mở frontend bằng HTTP server.

## Quickstart & Local Development

Các lệnh dưới đây dành cho **PowerShell trên Windows**. Mỗi terminal bắt đầu tại **gốc repo `G1_Web_Design`**. Dùng một venv backend tại `.venv/`; không tạo thêm `apps/api/.venv/`.

### Chỉ xem giao diện

```powershell
python -m http.server 8085 --bind 127.0.0.1 --directory apps/web
```

Mở **http://127.0.0.1:8085**. Khi chưa có backend, trang vẫn cho xem chế độ khách; đăng nhập, quản lý PDF và hỏi đáp cần các dịch vụ bên dưới. Không mở `index.html` bằng `file://`: frontend tải các phần `html/*.html` bằng Fetch và dùng ES modules.

### 1. Clone & Branch

```powershell
git clone https://github.com/teddywristh/G1_Web_Design.git
Set-Location G1_Web_Design
git switch -c feat/your-feature-name
```

Nếu đã có repo, dùng thư mục hiện tại và bỏ bước clone.

### 2. Environment Configuration

Chỉ tạo venv và sao chép cấu hình khi chưa tồn tại:

```powershell
if (!(Test-Path .venv/Scripts/python.exe)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r apps/api/requirements-dev.txt
if (!(Test-Path apps/api/.env)) { Copy-Item apps/api/.env.example apps/api/.env }
npm.cmd install --global firebase-tools@15.12.0
```

Backend tự đọc `apps/api/.env`, không đọc file `.env` ở gốc để thay thế. Giữ cấu hình có sẵn và kiểm tra các giá trị local sau:

```dotenv
FIREBASE_PROJECT_ID=demo-legal-api
FIREBASE_STORAGE_BUCKET=demo-legal-api.appspot.com
FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
FIRESTORE_EMULATOR_HOST=127.0.0.1:8081
STORAGE_EMULATOR_HOST=http://127.0.0.1:9198
BACKEND_CORS_ORIGINS=["http://127.0.0.1:8085"]
AUTH_COOKIE_SECURE=false
```

Không ghi đè cấu hình cloud hiện có bằng mẫu emulator. Không commit `.env` hoặc key thật.

### 3. Start Firebase Emulator

**Terminal 1**, từ gốc repo:

```powershell
firebase.cmd emulators:start --project demo-legal-api --only auth,firestore,storage --export-on-exit .emulator-data
```

Nếu đã có `.emulator-data/firebase-export-metadata.json`, dùng lệnh khôi phục:

```powershell
firebase.cmd emulators:start --project demo-legal-api --only auth,firestore,storage --import .emulator-data --export-on-exit .emulator-data
```

Đợi cả ba emulator sẵn sàng. Dừng bằng `Ctrl+C` và đợi export xong để giữ tài khoản/tài liệu cho lần sau. Tài khoản emulator tách biệt tài khoản cloud.

### 4. Start Backend API (FastAPI)

**Terminal 2**, từ gốc repo:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --reload --reload-dir apps/api/app --port 8000
```

- Health: http://127.0.0.1:8000/health
- Kiểm tra Firestore/Storage: http://127.0.0.1:8000/ready
- Swagger: http://127.0.0.1:8000/docs

`--app-dir apps/api` cho phép chạy từ gốc repo. Nếu đã đứng trong `apps/api`, đường dẫn tương ứng là `app.main:app --reload --reload-dir app`; không trộn hai cách chạy.

### 5. Start the Ingestion Worker

**Terminal 3**, từ gốc repo, dùng cùng venv và cấu hình với API:

```powershell
$env:PYTHONPATH = (Resolve-Path apps/api).Path
.\.venv\Scripts\python.exe -m app.workers.ingestion
```

Không chạy worker thì PDF dừng ở hàng đợi. Mẫu `apps/api/.env.example` hiện chọn `EMBEDDING_PROVIDER=local`, URL `http://127.0.0.1:8010`; cần khởi động embedding host và đợi `/ready` trả 200. Xem [cài/chạy Nemotron](apps/embedding/README.md). Host dùng môi trường riêng; không cài PyTorch/model vào venv backend chỉ để mở web.

Có thể chọn `openai` hoặc `openrouter` thay cho `local` trong `apps/api/.env` nếu đã cấu hình model, dimensions và key tương ứng. API và worker phải dùng cùng profile. Model trả lời hỏi đáp được cấu hình riêng với embedding; có embedding chưa có nghĩa là đã có kết nối LLM. Xem [knowledge/RAG](docs/knowledge-rag.md) và [kết nối AI](docs/ai-connections.md).

Để lưu API key qua màn hình Thiết lập, cấu hình `AI_CREDENTIAL_ENCRYPTION_KEY` trong `apps/api/.env`. Nếu chưa có, tạo một lần bằng lệnh dưới và giữ giá trị ổn định cho API/worker; không tạo lại mỗi lần khởi động:

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 6. Start Frontend Web (static HTML)

**Terminal 4**, từ gốc repo:

```powershell
python -m http.server 8085 --bind 127.0.0.1 --directory apps/web
```

Mở **http://127.0.0.1:8085**. Dùng `127.0.0.1` cho cả web và API để cookie phiên nhất quán. API URL nằm trong `<meta name="api-base">` của `apps/web/index.html`; nếu đổi cổng web, cập nhật cả `BACKEND_CORS_ORIGINS` và Google OAuth origin khi sử dụng.

Nếu terminal đang ở `apps/web`, chạy `python -m http.server 8085 --bind 127.0.0.1` hoặc `npm.cmd run dev`. Không thêm `--directory apps/web` khi đã đứng trong thư mục đó. `npm.cmd run dev` và `npm.cmd start` chỉ là lệnh tắt cho cùng static server; không cần `npm install` để chạy chúng. Hậu tố `.cmd` tránh lỗi PowerShell chặn `npm.ps1`/`firebase.ps1`, không cần đổi ExecutionPolicy.

Frontend hiện tại:

```text
apps/web/
├── index.html     Cấu hình và khung trang
├── html/          Màn hình, form và hộp thoại
├── css/main.css   Thứ tự tải các phần CSS
└── js/main.js     Ghép HTML rồi khởi tạo các module
```

Chi tiết file và luồng chức năng: [README frontend](apps/web/README.md). Bản Next.js trong `apps/web/src/` chỉ để tham khảo, dùng các npm script có hậu tố `:legacy` và không phục vụ giao diện HTML hiện tại.

### Kiểm tra sau khi chạy

| Thành phần | Địa chỉ/cách kiểm tra |
| --- | --- |
| Frontend | `http://127.0.0.1:8085` |
| Backend | `http://127.0.0.1:8000/health`, `/ready`, `/docs` |
| Firebase | Auth `9099`, Firestore `8081`, Storage `9198` |
| Embedding local | `http://127.0.0.1:8010/ready`, chỉ cần khi chọn provider local |
| Worker | Terminal có log nhận và xử lý job PDF |

Đăng ký tài khoản local, tạo kho riêng, tải PDF có lớp chữ, theo dõi xử lý rồi hỏi và mở trích dẫn. Chế độ khách chỉ xác nhận giao diện tải được, không xác nhận kết nối AI.

### Lỗi thường gặp

| Hiện tượng | Kiểm tra |
| --- | --- |
| Không tải được giao diện/404 HTML con | Dùng HTTP server và phục vụ đúng `apps/web`, không mở `html/chat.html` riêng. |
| Failed to fetch/không kết nối API | API cổng 8000 đang chạy, meta API đúng URL, CORS chứa đúng origin 8085; dùng cùng hostname. |
| Cổng đã được sử dụng | Dừng server cũ bằng `Ctrl+C`; không mở đồng thời Python server và `npm run dev` trên 8085. |
| PDF chờ xử lý/lỗi embedding | Kiểm tra terminal worker và provider; với local kiểm tra cổng 8010 `/ready`. |
| Tài khoản local biến mất | Khởi động emulator với bản export cũ bằng `--import .emulator-data`. |
| Cloud báo thiếu index | Theo [runbook](docs/backend-operations.md); emulator không xác nhận các index cloud đã sẵn sàng. |

macOS/Linux: dùng `npm`/`firebase` thay cho `npm.cmd`/`firebase.cmd`, dùng `.venv/bin/python` thay cho `.\.venv\Scripts\python.exe`; worker từ gốc repo chạy `PYTHONPATH=apps/api .venv/bin/python -m app.workers.ingestion`. Các script `.sh` dành cho Bash/WSL, không dán trực tiếp vào PowerShell. Docker/gateway và triển khai cloud có hướng dẫn riêng trong [runbook](docs/backend-operations.md).

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
chore(infra): update Firebase emulator configuration
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
- **Frontend**: static HTML/CSS/ES modules; see [the frontend structure and code map](apps/web/README.md). PowerShell: `Get-ChildItem apps/web/js/*.js | ForEach-Object { Get-Content -Raw $_.FullName | node --input-type=module --check }`. Bash: `for f in apps/web/js/*.js; do node --input-type=module --check < "$f"; done`.
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
