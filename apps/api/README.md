# Backend API

FastAPI + Firebase Authentication + Firestore + Firebase Storage. Backend MVP quản lý tài khoản và văn bản pháp luật. Module RAG từ nhánh AI_RAG được tích hợp riêng; các API MVP không cần OpenAI key.

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
- [Xác thực và quản lý phiên](../../docs/auth-plan.md): đăng ký bcrypt, Google Sign-In, cookie và cấu hình production.

## RAG integration

Module từ `AI_RAG` cung cấp `POST /api/v1/rag/ask` với body
`{"question": "Câu hỏi pháp luật", "top_k": 5}`. Endpoint yêu cầu phiên ứng dụng hoặc Firebase ID token
và profile đang active, theo cùng cơ chế xác thực của backend.

RAG đọc tối đa 100 chunk chuẩn bị sẵn từ Firestore `document_chunks`, xếp hạng
bằng embedding/keyword rồi sinh câu trả lời kèm nguồn; không đọc PDF trực tiếp
trong request. Chunk gồm `content` (hoặc `text`), `embedding`, `document_id`,
`document_title`, và metadata tùy chọn `article`, `clause`, `point`, `page_number`,
`source_url`. `core/database.py` dùng lại kết nối tại `core/firebase.py`.

Cấu hình `OPENAI_API_KEY` trong môi trường backend để sử dụng RAG. Model và
ngưỡng lấy từ các biến tương ứng trong `.env.example`. Khi thiếu key, request RAG
đã xác thực trả 503; các endpoint backend khác vẫn hoạt động. Giữ key ngoài Git.
Các test tích hợp route dùng AI giả lập, không gọi API tính phí.

## AI connection options

Xem [AI connections](../../docs/ai-connections.md) cho key cá nhân/key chung của OpenAI và Anthropic, cấu hình mã hóa, lựa chọn provider/source và trạng thái OAuth cho website hosted. `POST /api/v1/rag/ask` nhận thêm provider, credential_source, model và retrieval_mode; request cũ tiếp tục dùng mặc định OpenAI/auto/hybrid.

Engine OpenCode thử nghiệm cho API RAG bằng OpenAI API key: [cấu hình và giới hạn local](../../docs/ai-connections.md#engine-opencode-thử-nghiệm-local).
