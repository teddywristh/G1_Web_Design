# Backend API

FastAPI + Firebase Authentication + Firestore + Firebase Storage. Backend MVP quản lý tài khoản và văn bản pháp luật. Có thêm kho tài liệu riêng, worker ingestion và hỏi đáp RAG; các API MVP không cần OpenAI key.

## Chạy local

Chạy từ thư mục gốc repo, dùng Python 3.11+, Node 22+ và Java 21+. Tạo môi trường
Python, cài dependencies và cấu hình local (giữ nguyên `.env` nếu đã có):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements-dev.txt
test -e apps/api/.env || cp apps/api/.env.example apps/api/.env
npm install -g firebase-tools@15.12.0
```

Trong terminal riêng từ gốc repo, chạy emulator:

```bash
firebase emulators:start --project demo-legal-api --only auth,firestore,storage --export-on-exit .emulator-data
```

Nếu đã có `.emulator-data/firebase-export-metadata.json`, thêm `--import .emulator-data`
vào lệnh để khôi phục dữ liệu. Dừng emulator bằng Ctrl+C và đợi export xong.
Trong hai terminal khác từ gốc repo, chạy API và worker:

```bash
source .venv/bin/activate
python -m uvicorn app.main:app --app-dir apps/api --reload --reload-dir apps/api/app --port 8000
```

```bash
source .venv/bin/activate
cd apps/api
python -m app.workers.ingestion
```

Đợi emulator báo sẵn sàng trước khi chạy API và worker. Dừng API/worker cloud cũ
trước để tránh trùng cổng hoặc hai worker chạy hai môi trường. Truy cập web tại
`http://127.0.0.1:8085`, đăng xuất nếu cần và đăng ký tài khoản local mới: Auth,
Firestore và Storage emulator có dữ liệu riêng, không sao chép tài khoản hay tài liệu cloud.
Dữ liệu được lưu trong `.emulator-data/` khi export; dùng `--import` để khôi phục.
Nếu bị tắt đột ngột, dữ liệu từ lần chạy đó có thể bị mất.
Các cấu hình khác, gồm embedding provider và key, vẫn lấy từ `apps/api/.env`; xử lý
embedding có thể gọi dịch vụ bên ngoài theo cấu hình đó. Firestore emulator không hỗ trợ
kiểm thử tìm kiếm vector thực tế như cloud.

Với OpenRouter model `:free`, worker và API dùng cùng bộ đếm trên Firestore: tối đa
40 request mỗi 24 giờ trượt, cách nhau ít nhất 5 giây cho cùng một key. Mỗi chunk
đã xử lý được lưu để job tiếp tục sau khi chờ. Số lượt dùng từ ứng dụng khác dùng
cùng tài khoản không nằm trong bộ đếm này, vì vậy OpenRouter vẫn có thể trả 429.
Khi đó worker lùi lịch và không tính vào giới hạn số lần lỗi thông thường.

Mỗi tài liệu được embedding toàn bộ các đoạn. Tiến độ xuất hiện trong thư viện; khi
job gián đoạn, các đoạn đã lưu được dùng lại. Với PDF scan, worker OCR cục bộ bằng
Tesseract (ngôn ngữ `vie+eng`) và `pdftoppm`; cài các gói `tesseract-ocr`,
`tesseract-ocr-vie`, `tesseract-ocr-eng`, `poppler-utils`. Biến `OCR_BINARY`,
`OCR_TESSDATA_DIR`, `OCR_LANGUAGES` cho phép cấu hình đường dẫn và ngôn ngữ.
Chọn Xử lý lại trên tài liệu đã tải để tạo lại chỉ mục sau khi bật OCR.

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

### Hỏi khi tài liệu chưa xử lý xong

Người dùng có thể gửi câu hỏi không chọn kho, hoặc chọn kho đang xử lý. Khi PDF đã
được đọc, có thể tra theo số điều trước khi hoàn thành embedding; kết quả có cảnh báo
tài liệu đang xử lý. Đây không phải tìm kiếm toàn văn. Nếu dịch vụ embedding bị giới
hạn, hệ thống vẫn thử tra số điều và web khi người dùng bật tìm web.

Tìm web chính thức mặc định dùng API tìm kiếm công khai của Cổng Công báo và đọc
PDF gốc, không cần key tìm kiếm; VBPL là nguồn dự phòng. Bật `OFFICIAL_WEB_ENABLED=true`
trong `apps/api/.env`; mẫu local đã bật cờ này. Nếu các nguồn không phản hồi
hoặc thay đổi giao diện, hệ thống báo không tìm được nguồn.
Tùy chọn cấu hình `BRAVE_SEARCH_API_KEY` để thay VBPL search bằng Brave; Brave có
thể tính phí. Người dùng chọn tìm web cho từng câu hỏi. Chỉ câu hỏi được gửi đi
tìm kiếm, không gửi PDF. OpenRouter key dùng cho embedding không liên quan tìm web.

PDF tải lên được xử lý nền bởi worker riêng (cần chạy cùng emulator và API):

```bash
cd apps/api && python -m app.workers.ingestion
```

`POST /api/v1/rag/ask` chạy workflow trong `services/qa.py`: chọn kho (`knowledge_base_ids`, tối đa 5), tra theo số hiệu/điều và vector, kiểm tra lại nguồn rồi trả lời kèm trích dẫn. Embedding dùng OpenAI hoặc OpenRouter theo cấu hình backend, độc lập với model trả lời. Chi tiết, cờ tính năng, điều kiện dữ liệu và giới hạn: [docs/knowledge-rag.md](../../docs/knowledge-rag.md). Giữ key ngoài Git. Test dùng AI giả lập, không gọi API tính phí; emulator không chạy `find_nearest`, nên chỉ mục vector cần kiểm tra trên dự án Firebase thật.

Nếu dùng Firebase cloud thay vì emulator, tạo các index trong `infra/firebase/firestore.indexes.json`
trước khi chạy worker và chờ trạng thái **Ready**. Truy vấn nhận job cần composite index
`processing_jobs` với `status` và `nextRunAt` tăng dần; danh sách tài liệu và tìm kiếm vector
cũng cần index riêng. Các index `provision_versions` trong file này phục vụ tra số điều ngay
sau khi parse; emulator không xác nhận các index cloud đã được triển khai. Lệnh deploy index của Firebase chạy từ gốc repo và có thể yêu cầu xác nhận
thay đổi index hiện có, nên hãy đọc kỹ các prompt. Lỗi `FAILED_PRECONDITION: The query requires
an index` nghĩa là index tương ứng chưa có hoặc chưa build xong, không phải lỗi khởi động FastAPI.

## AI connection options

Xem [AI connections](../../docs/ai-connections.md) cho key cá nhân/key chung của OpenAI, Anthropic, DeepSeek và OpenRouter, cấu hình mã hóa, lựa chọn provider/source và trạng thái OAuth cho website hosted. `GET /api/v1/ai/models` liệt kê model theo từng kết nối; `POST /api/v1/rag/ask` nhận provider, credential_source và model, luôn chạy qua OpenCode.

OpenCode worker cho API RAG: [cấu hình local và hosted](../../docs/ai-connections.md#opencode-worker).
