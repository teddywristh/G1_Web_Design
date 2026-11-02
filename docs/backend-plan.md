# Kế hoạch thiết kế backend — không bao gồm LLM/AI

Implementation backend trong repository đã hoàn thành và được xác minh bằng 33 test trên container Python 3.11 + Firebase Emulator. Xem [kết quả kiểm tra](backend-verification.md), [API contract](api-contract.md) và [runbook](backend-operations.md). Các bước cấu hình/triển khai cloud và diễn tập restore thực tế vẫn là bước vận hành trước release, chưa chạy trên tài khoản cloud.

## 1. Mục tiêu và phạm vi

Xây dựng backend MVP cho việc quản lý và tra cứu văn bản pháp luật, dựa trên code hiện có trong `apps/api`. Tài liệu này là phạm vi thiết kế gốc; hành vi đã triển khai được mô tả trong API contract.

**Trong phạm vi:** xác thực, hồ sơ người dùng, phân quyền, metadata văn bản, upload/download PDF, tra cứu theo metadata, quản trị người dùng, nhật ký quản trị, kiểm thử và vận hành API.

**Ngoài phạm vi:** LLM, chatbot, lịch sử hội thoại/message, prompt, RAG, embedding, vector database, semantic search, sinh tóm tắt, trích dẫn tự động, OCR và pipeline phân tích nội dung tài liệu. Không tạo backlog hoặc phụ thuộc triển khai cho các phần này.

Giả định MVP: tra cứu yêu cầu đăng nhập; chỉ admin được quản lý văn bản; không triển khai phân quyền theo tổ chức hoặc thanh toán.

## 2. Hiện trạng và khoảng trống

| Thành phần | Hiện trạng trong repository | Việc cần làm |
|---|---|---|
| FastAPI | `main.py` có `GET /health` | Router `/api/v1`, dependency injection, error handler, CORS |
| Xác thực | Có `verify_firebase_token`, `require_admin` | Tích hợp vào route, kiểm tra tài khoản bị khóa cho mọi API bảo vệ |
| Firestore | Có repository cơ bản cho user và văn bản | Schema validation, query có thứ tự, cursor, xử lý xung đột |
| Storage | Có service upload/download/delete/signed URL | API upload, xác minh file, kiểm soát quyền và lỗi giữa Storage/Firestore |
| Kiểm thử | Có test repository và Firebase Storage | Test API, quyền truy cập và tích hợp Auth/Firestore/Storage qua emulator |
| CI | Có compile và pytest | Kiểm tra lint, chạy bộ test tích hợp có emulator |
| Tài liệu | Kế hoạch mới theo Firebase; README và một phần sơ đồ còn nhắc PostgreSQL/Redis | Đồng bộ tài liệu để có một hướng triển khai MVP |

Các helper và repository hiện có là nền tảng để mở rộng, chưa được coi là chức năng API hoàn chỉnh.

## 3. Kiến trúc dự kiến

Giữ hướng **FastAPI + Firebase Authentication + Firestore + Firebase Storage** đã ghi trong `docs/plans.md`. Không bổ sung database hoặc cache mới trong giai đoạn này.

```text
Web → Firebase Authentication → ID token
Web → FastAPI /api/v1 → Auth dependencies → Router → Service
                                                     ├─ Repository → Firestore
                                                     └─ Storage service → Firebase Storage
```

- **Router:** nhận request, validate schema, gọi service, trả HTTP response.
- **Service:** xử lý nghiệp vụ, quyền truy cập và phối hợp các thao tác dữ liệu.
- **Repository:** truy vấn Firestore; không chứa HTTP exception.
- **Core/dependencies:** cấu hình, khởi tạo Firebase, current user, quyền admin, request ID.
- Backend là điểm truy cập dữ liệu nghiệp vụ. Firebase Client SDK chỉ phục vụ đăng nhập; frontend không tự đọc/ghi Firestore hoặc Storage.
- Dùng một luồng khởi tạo Firebase chung; rà soát phần trùng giữa `core/firebase.py` và `services/firebase_storage.py`.
- Với SDK đồng bộ, dùng route/dependency đồng bộ hoặc đưa thao tác blocking vào thread pool; không chặn event loop bằng lời gọi SDK trực tiếp trong `async def`.

Thư mục bổ sung dự kiến:

```text
apps/api/app/
├── api/v1/          # router: users, documents, admin
├── schemas/         # request/response Pydantic
├── services/        # user, document, audit, storage
├── repositories/    # mở rộng repository hiện có
├── core/            # config, Firebase, auth, errors
└── dependencies.py
```

## 4. Mô hình dữ liệu và quy tắc nghiệp vụ

| Collection | Dữ liệu chính | Quy tắc |
|---|---|---|
| `users/{uid}` | email, displayName, role, isActive, createdAt, updatedAt | UID từ token; role mặc định `user`; client chỉ sửa displayName |
| `legal_documents/{id}` | title, normalizedTitle, documentNumber, documentType, issuingAuthority, issueDate, effectiveDate, status, sourceUrl, storagePath, fileSize, contentType, fileState, createdBy, updatedBy, createdAt, updatedAt, deletedAt | Metadata nhập thủ công; đường dẫn file do server sinh; chỉ admin ghi |
| `system_logs/{id}` | event, actorId, targetId, result, requestId, createdAt | Backend ghi; admin đọc; không lưu token hoặc nội dung PDF |

- Chốt enum `status` trong API contract, dự kiến `not_yet_effective`, `effective`, `partially_expired`, `expired`. Trạng thái do admin cập nhật từ nguồn kiểm chứng; backend không tự suy luận hiệu lực từ ngày tháng.
- `fileState`: `pending_upload`, `available`, `upload_failed`, `deletion_pending`, `deleted`; chỉ phản ánh lưu trữ file. Không dùng `processingStatus` để điều khiển nghiệp vụ này.
- Ngày văn bản dùng `YYYY-MM-DD`; timestamp nghiệp vụ dùng server timestamp và trả ISO 8601 UTC.
- Chuẩn hóa số hiệu và tên để tra cứu; không mặc định số hiệu là duy nhất nếu chưa chốt khóa nghiệp vụ.
- `storagePath`, role, actor và timestamp là trường server quản lý. Không cho request body cập nhật tùy ý.
- Không đổi hoặc xóa các collection/trường đang dành cho tính năng ngoài phạm vi.
- Mỗi truy vấn danh sách có `limit` mặc định 20, tối đa 100, thứ tự ổn định và cursor gồm khóa sắp xếp + document ID. Cursor gắn với bộ lọc, sai định dạng trả lỗi validation.
- Lập ma trận query trước khi thêm composite index. Không tạo index cho mọi tổ hợp bộ lọc; không tải toàn bộ collection để lọc tại Python.

## 5. API contract dự kiến

Các endpoint nghiệp vụ dùng prefix `/api/v1`. Giữ `/health` cho kiểm tra tiến trình; bổ sung `/ready` cho kiểm tra khả năng phục vụ, timeout ngắn và không lộ cấu hình.

| Method | Endpoint | Quyền | Hành vi |
|---|---|---|---|
| POST | `/users/me/bootstrap` | Token hợp lệ | Tạo hồ sơ mặc định nếu chưa tồn tại; gọi lại không đổi role/isActive |
| GET / PATCH | `/users/me` | User hoạt động | Xem hồ sơ / sửa displayName |
| GET | `/documents` | User hoạt động | Danh sách và lọc văn bản đã có file, chưa xóa |
| GET | `/documents/{id}` | User hoạt động | Chi tiết metadata |
| GET | `/documents/{id}/download` | User hoạt động | Cấp signed URL thời hạn ngắn hoặc stream qua backend |
| POST | `/admin/documents` | Admin | Tạo metadata, `fileState=pending_upload` |
| PUT | `/admin/documents/{id}/file` | Admin | Upload PDF cho bản ghi đang chờ; retry an toàn |
| PATCH | `/admin/documents/{id}` | Admin | Sửa các trường metadata được phép |
| DELETE | `/admin/documents/{id}` | Admin | Ẩn bản ghi và bắt đầu quy trình xóa file |
| GET | `/admin/documents` | Admin | Xem cả bản nháp và upload lỗi để xử lý |
| GET | `/admin/users` | Admin | Danh sách người dùng có phân trang |
| PATCH | `/admin/users/{uid}` | Admin | Khóa/mở tài khoản; MVP chưa mở API cấp role |
| GET | `/admin/audit-logs` | Admin | Tra cứu nhật ký có phân trang |

Đăng ký, đăng nhập, reset mật khẩu và refresh token dùng Firebase Authentication; không viết thêm hệ thống lưu mật khẩu hoặc phát hành token riêng. Admin đầu tiên được cấp bằng script quản trị có kiểm soát, không qua public API. Không cho admin tự khóa tài khoản trong MVP.

Tra cứu MVP hỗ trợ số hiệu chính xác, tiền tố tên đã chuẩn hóa và các bộ lọc được công bố trong contract như loại văn bản, cơ quan, trạng thái, khoảng ngày. Mỗi chế độ có thứ tự sắp xếp xác định; frontend chỉ gửi tổ hợp được hỗ trợ. Tìm kiếm toàn văn/từ khóa ở vị trí bất kỳ chưa nằm trong cam kết MVP.

Response danh sách dùng `{ items, nextCursor }`. Lỗi dùng `{ error: { code, message }, requestId }`; thống nhất 401, 403, 404, 409, 413, 415, 422 và 503. Schema response phải loại bỏ trường nội bộ không cần cho client.

## 6. Luồng upload và xóa PDF

**Upload:** tạo metadata → kiểm tra quyền và trạng thái → đọc file theo từng phần với giới hạn dung lượng → kiểm tra MIME, đuôi file và chữ ký PDF → upload vào đường dẫn server sinh → cập nhật metadata thành `available` → ghi audit.

- Mốc dung lượng dự kiến 20 MiB, cấu hình tập trung; kiểm soát cả ở HTTP và lúc đọc stream, không chỉ tin `Content-Length`.
- Kiểm tra chữ ký file không được coi là kiểm tra toàn vẹn hoặc quét mã độc. MVP phục vụ PDF do admin tin cậy tải lên, không có upload công khai.
- Không nhận `storagePath` tùy ý từ client. Cố định object theo document ID và dùng cơ chế điều kiện ghi để tránh upload đồng thời ghi đè nhau.
- Storage và Firestore không có transaction chung: upload lỗi để lại trạng thái retry được; file đã upload nhưng cập nhật metadata lỗi phải có bước đối soát hoặc dọn file mồ côi.
- Dùng điều kiện phiên bản/precondition cho cập nhật trạng thái; request cạnh tranh trả 409. Ghi nhận kết quả theo document ID để retry không tạo thêm object.
- Download chỉ cấp quyền sau khi kiểm tra user và trạng thái tài liệu. Signed URL dự kiến 5 phút; URL đã cấp còn dùng được đến khi hết hạn. Nếu cần thu hồi truy cập ngay, chọn stream qua backend.

**Xóa:** đánh dấu `deletedAt` để ẩn khỏi truy vấn → chuyển `deletion_pending` → xóa object → chuyển `deleted`. Thất bại giữ trạng thái để retry, không khôi phục hiển thị tự động. Trước release phải có lệnh đối soát có thể chạy lại, xử lý cả file mồ côi và xóa còn dang dở; không đòi hỏi message broker cho MVP.

## 7. Thứ tự triển khai và tiêu chí nghiệm thu

Ước lượng dưới đây là ngày công cho một lập trình viên backend quen dự án; chưa bao gồm thời gian chờ review, cấp quyền cloud hoặc tích hợp frontend.

| Giai đoạn | Công việc / đầu ra | Điều kiện hoàn thành | Ước lượng |
|---|---|---|---|
| 1 — Contract | Viết `docs/api-contract.md`, chốt enum, query/index, quyền, schema và đồng bộ tài liệu Firebase | Frontend có request/response mẫu; mọi endpoint có quyền và mã lỗi rõ ràng | 1–2 ngày |
| 2 — Nền tảng | Router, schemas, dependency injection, Firebase init chung, error handler, CORS, health/readiness | API khởi động bằng emulator; lỗi chuẩn hóa; readiness lỗi không báo thành công | 1–2 ngày |
| 3 — Tài khoản | Bootstrap idempotent, current user, role guard, khóa/mở user, script cấp admin | Token sai trả 401; tài khoản khóa bị chặn; user không tự nâng quyền | 2 ngày |
| 4 — Văn bản | CRUD metadata, query/cursor, indexes, upload/download/xóa và đối soát | Admin tạo và upload PDF; user tìm/xem/tải; lỗi giữa Storage/Firestore retry được | 3–4 ngày |
| 5 — Quản trị | Danh sách user, audit log, kiểm soát cập nhật đồng thời | Sửa/xóa/khóa có actor và kết quả; log không lộ dữ liệu nhạy cảm | 1–2 ngày |
| 6 — Kiểm thử và bàn giao | API/integration tests, CI, Docker, cấu hình dev/prod, runbook và smoke test | Luồng đầu cuối qua emulator và môi trường dev riêng chạy được; tài liệu khớp API | 2–3 ngày |

**Tổng dự kiến: 10–15 ngày công.** Thứ tự phụ thuộc: 1 → 2 → 3 → 4 → 5 → 6. Viết test theo từng giai đoạn; giai đoạn 6 tập trung tích hợp và bàn giao. Chưa triển khai tính năng tiếp theo trước khi các điều kiện nghiệm thu tương ứng đạt.

## 8. Kiểm thử và vận hành

- Unit test: bootstrap lặp lại không nâng quyền, allowlist cập nhật, chuẩn hóa metadata, validation upload, chuyển trạng thái khi lỗi và retry.
- API test: thiếu/token hết hạn, user gọi route admin, tài khoản bị khóa, tài liệu đã xóa, cursor sai và không rò rỉ trường nội bộ.
- Integration test qua emulator: token → hồ sơ → admin upload → user tra cứu/tải → xóa; phân trang không lặp khi giá trị sắp xếp trùng; upload cạnh tranh; lỗi Storage/Firestore và đối soát.
- Test rules riêng để xác nhận client không thể truy cập trực tiếp dữ liệu; test Admin SDK không thay thế test rules.
- CI chạy lint, compile, unit/API test và integration test bằng emulator, không cần credential production.
- Trước release: smoke test signed URL trên dev thật vì emulator không xác minh đầy đủ cơ chế ký và IAM; nếu chọn stream thì kiểm tra giới hạn tài nguyên và tải file.
- Cấu hình CORS theo allowlist, request ID, log có cấu trúc và timeout; giới hạn tốc độ cho API bằng lớp gateway hoặc hạ tầng triển khai dùng chung giữa các instance.
- Tách dev/prod, dùng runtime service account quyền tối thiểu; kiểm tra startup để tránh emulator host trong production. Không deploy thật trong phạm vi lập kế hoạch này.
- Runbook gồm kiểm tra quota/lỗi, rollback phiên bản API, retry/dọn file, cấu hình sao lưu và diễn tập khôi phục Firestore/Storage trước phát hành.

## 9. Mốc hoàn thành MVP

MVP hoàn thành khi người dùng có thể đăng nhập, xem hồ sơ, tra cứu metadata và tải PDF; admin có thể quản lý tài liệu, khóa/mở tài khoản và xem nhật ký. Các API bảo vệ kiểm tra quyền trên server, danh sách có cursor, upload/xóa có đường phục hồi lỗi, CI qua emulator đạt và có hướng dẫn chạy local/deploy/khôi phục. Toàn bộ luồng này hoạt động độc lập với tính năng AI.
