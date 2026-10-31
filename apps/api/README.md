# Backend API

FastAPI + Firebase Authentication + Firestore + Firebase Storage. Backend MVP quản lý tài khoản và văn bản pháp luật; không phụ thuộc tính năng AI.

## Chạy local

Từ thư mục gốc repo, dùng Python 3.11+, Node 22+, Java 21+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements-dev.txt
cp apps/api/.env.example apps/api/.env
npm install -g firebase-tools@15.12.0
firebase emulators:start --project demo-legal-api --only auth,firestore,storage
```

Terminal khác:

```bash
source .venv/bin/activate
uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

Health: `/health`; dependency readiness: `/ready`; Swagger: `/docs`. File `.env` luôn đọc theo `apps/api/.env`, không phụ thuộc cwd. Env process có ưu tiên cao hơn file. Demo project bắt buộc đủ ba emulator. Không dùng cấu hình production cho phát triển local.

## Kiểm tra

```bash
ruff check apps/api scripts/backend_admin.py
ruff format --check apps/api scripts/backend_admin.py
python -m compileall apps/api/app scripts/backend_admin.py
python -m pytest -m 'not integration' -q
firebase emulators:exec --project demo-legal-api --only auth,firestore,storage 'RUN_FIREBASE_INTEGRATION=1 python -m pytest -m integration -q'
```

Test tự cố định các host 127.0.0.1 và project demo-legal-api. Không có emulator thì test integration được skip; không fallback sang cloud. CI chạy cả hai bộ test.

## Tài liệu

- [API contract](../../docs/api-contract.md): endpoint, request/response, query, phiên bản và mã lỗi.
- [Runbook](../../docs/backend-operations.md): admin provisioning, đối soát, triển khai, khôi phục.
- [Data schema](../../docs/database-schema.md).
- [Kế hoạch phạm vi](../../docs/backend-plan.md).
