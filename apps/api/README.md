# Backend API

FastAPI + Firebase Authentication + Firestore + Firebase Storage. Backend MVP quản lý tài khoản và văn bản pháp luật. Có thêm kho tài liệu riêng, worker ingestion và hỏi đáp RAG; các API MVP không cần OpenAI key.

## Chạy local

Từ thư mục gốc repo, dùng Python 3.11+, Node 22+, Java 21+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements-dev.txt
test -e apps/api/.env || cp apps/api/.env.example apps/api/.env
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
ruff check apps/api scripts/backend_admin.py scripts/migrate_knowledge.py scripts/evaluate_legal_qa.py
ruff format --check apps/api scripts/backend_admin.py scripts/migrate_knowledge.py scripts/evaluate_legal_qa.py
python -m compileall apps/api/app scripts
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

## Worker và RAG

PDF tải lên được xử lý nền bởi worker riêng (cần chạy cùng emulator và API):

```bash
cd apps/api && python -m app.workers.ingestion
```

`POST /api/v1/rag/ask` chạy workflow trong `services/qa.py`: chọn kho (`knowledge_base_ids`, tối đa 5), tra theo số hiệu/điều và vector, kiểm tra lại nguồn rồi trả lời kèm trích dẫn. Embedding luôn dùng OpenAI; thiếu khóa thì request RAG trả 503. Chi tiết, cờ tính năng, vận hành và giới hạn: [docs/knowledge-rag.md](../../docs/knowledge-rag.md). Giữ key ngoài Git. Test dùng AI giả lập, không gọi API tính phí; emulator không chạy `find_nearest`, nên chỉ mục vector cần kiểm tra trên dự án Firebase thật.

Nếu dùng Firebase cloud thay vì emulator, tạo các index trong `infra/firebase/firestore.indexes.json`
trước khi chạy worker và chờ trạng thái **Ready**. Truy vấn nhận job cần composite index
`processing_jobs` với `status` và `nextRunAt` tăng dần; danh sách tài liệu và tìm kiếm vector
cũng cần index riêng. Lệnh deploy index của Firebase chạy từ gốc repo và có thể yêu cầu xác nhận
thay đổi index hiện có, nên hãy đọc kỹ các prompt. Lỗi `FAILED_PRECONDITION: The query requires
an index` nghĩa là index tương ứng chưa có hoặc chưa build xong, không phải lỗi khởi động FastAPI.

## AI connection options

Xem [AI connections](../../docs/ai-connections.md) cho key cá nhân/key chung của OpenAI và Anthropic, cấu hình mã hóa, lựa chọn provider/source và trạng thái OAuth cho website hosted. `POST /api/v1/rag/ask` nhận thêm provider, credential_source, model và retrieval_mode; request cũ tiếp tục dùng mặc định OpenAI/auto/hybrid.

Engine OpenCode thử nghiệm cho API RAG bằng OpenAI API key: [cấu hình và giới hạn local](../../docs/ai-connections.md#engine-opencode-thử-nghiệm-local).
