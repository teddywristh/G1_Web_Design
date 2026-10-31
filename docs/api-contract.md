# Backend API contract v1

Backend MVP này hoạt động độc lập với AI. Đặc tả máy đọc được nằm tại `GET /openapi.json`; Swagger UI tại `/docs`. Các payload nghiệp vụ dùng camelCase và từ chối trường không được khai báo.

## Xác thực và phiên bản

Frontend đăng ký/đăng nhập/reset mật khẩu bằng Firebase Authentication, gửi `Authorization: Bearer <ID_TOKEN>` vào API. Backend kiểm tra token và trạng thái thu hồi/khóa trên Firebase, đồng thời kiểm tra `users/{uid}.isActive` cho mọi API nghiệp vụ. Không dùng role từ token/request để cấp quyền.

Sau đăng nhập gọi `POST /api/v1/users/me/bootstrap` không có body. Lần đầu tạo profile role `user`, active; gọi lại không thay đổi role, active hoặc version. Tài khoản bị khóa không thể bootstrap để tự mở khóa. Chỉ CLI cấp quyền admin.

GET chi tiết và các response ghi trả `ETag: "<version>"`. PATCH, DELETE và PUT file yêu cầu `If-Match: "<version>"`. Thiếu trả 428, sai định dạng trả 422, phiên bản cũ trả 409. Khi xung đột, tải lại bản ghi trước khi quyết định gửi lại thay đổi. Retry upload cùng SHA-256 khi file đã available và retry xóa khi đã deleted trả lại trạng thái hiện tại, không tạo thêm file hoặc audit.

## Endpoint

| Method | URL | Quyền / đầu vào | Kết quả |
|---|---|---|---|
| GET | `/health` | Công khai | 200 khi tiến trình đang chạy |
| GET | `/ready` | Công khai | 200 khi Firestore đọc được và bucket truy cập được; lỗi 503, timeout mỗi dependency 2 giây |
| POST | `/api/v1/users/me/bootstrap` | Token | 200 User |
| GET | `/api/v1/users/me` | Active | 200 User |
| PATCH | `/api/v1/users/me` | Active, If-Match, `{displayName}` | 200 User |
| GET | `/api/v1/documents` | Active, query bên dưới | 200 DocumentPage; chỉ file available, chưa xóa |
| GET | `/api/v1/documents/{id}` | Active | 200 Document / 404 |
| GET | `/api/v1/documents/{id}/download` | Active | PDF attachment qua backend; không cấp URL công khai |
| GET | `/api/v1/admin/documents` | Admin, query bên dưới | 200 DocumentPage; gồm nháp/lỗi/đã xóa |
| GET | `/api/v1/admin/documents/{id}` | Admin | 200 Document, gồm mọi trạng thái / 404 |
| POST | `/api/v1/admin/documents` | Admin, DocumentCreate | 201 Document + Location |
| PATCH | `/api/v1/admin/documents/{id}` | Admin, If-Match, metadata cần sửa | 200 Document |
| PUT | `/api/v1/admin/documents/{id}/file` | Admin, If-Match, raw PDF | 200 Document |
| DELETE | `/api/v1/admin/documents/{id}` | Admin, If-Match | 200 Document; có thể trả 503 và để deletion_pending cho retry |
| GET | `/api/v1/admin/users` | Admin, limit/cursor/isActive | 200 UserPage |
| PATCH | `/api/v1/admin/users/{uid}` | Admin, If-Match, `{isActive}` | 200 User; không sửa trạng thái chính mình |
| GET | `/api/v1/admin/audit-logs` | Admin, limit/cursor/event | 200 AuditPage |

`Active` yêu cầu profile đã bootstrap. Admin cũng phải active. API không triển khai đăng nhập, phát hành token, cấp role, xóa tài khoản Firebase hoặc bất kỳ endpoint chat nào.

## Payload và response

DocumentCreate (tất cả trường bắt buộc trừ effectiveDate/sourceUrl):

```json
{
  "title": "Luật mẫu",
  "documentNumber": "01/2026/QH",
  "documentType": "law",
  "issuingAuthority": "Cơ quan ban hành",
  "issueDate": "2026-01-01",
  "effectiveDate": "2026-02-01",
  "status": "effective",
  "sourceUrl": "https://example.com/van-ban"
}
```

Status: `not_yet_effective`, `effective`, `partially_expired`, `expired`. Admin xác minh thủ công trạng thái, không tự suy ra từ effectiveDate. Ngày theo YYYY-MM-DD, timestamp UTC ISO 8601. `sourceUrl` chỉ là metadata URL HTTP(S); backend không tải URL đó.

PATCH document nhận tập con các trường create, ít nhất một trường. Chỉ effectiveDate/sourceUrl được phép null. Không nhận storagePath, fileState, role, actor, version hay timestamps trong body.

Document response gồm id, metadata ở trên, fileState, fileSize, contentType, createdAt, updatedAt, deletedAt, version. Không trả đường dẫn Storage, checksum, upload lease hoặc actor nội bộ. User response gồm id, email, displayName, role, isActive, timestamps, version. Audit response gồm id, event, actorId, targetId, result, requestId, createdAt.

Danh sách:

```json
{"items": [], "nextCursor": null}
```

## Query và index

`limit`: 1–100, mặc định 20. `cursor`: opaque, lấy từ nextCursor, giữ nguyên bộ lọc khi gọi trang tiếp theo. Thứ tự có document ID làm khóa phụ để phân trang khi trùng giá trị. Đây là phân trang trên dữ liệu đang thay đổi, không bảo đảm snapshot nhất quán nếu trường sắp xếp bị sửa giữa hai request.

Chỉ dùng **một** chế độ lọc văn bản mỗi request; các tổ hợp khác trả 422:

| Chế độ | Query | Thứ tự |
|---|---|---|
| Tất cả | Không có selector | createdAt giảm dần, ID giảm dần |
| Số hiệu chính xác | documentNumber | createdAt giảm dần, ID giảm dần |
| Tiền tố tên | titlePrefix | normalizedTitle tăng dần, ID tăng dần |
| Loại | documentType | createdAt giảm dần, ID giảm dần |
| Cơ quan | issuingAuthority | createdAt giảm dần, ID giảm dần |
| Hiệu lực | status | createdAt giảm dần, ID giảm dần |
| Khoảng ngày ban hành | issueDateFrom và/hoặc issueDateTo | issueDate giảm dần, ID giảm dần |

Tên/số hiệu được chuẩn hóa chữ thường, bỏ dấu tiếng Việt, gộp khoảng trắng. Type/authority so khớp chính xác, có phân biệt hoa thường. Public query luôn thêm `deletedAt == null` và `fileState == available`. Index tương ứng được khai báo tại `infra/firebase/firestore.indexes.json`; emulator không thay thế bước xác nhận index đã build trên môi trường dev.

Users và audit sắp xếp createdAt giảm dần + ID giảm dần. Users có một bộ lọc isActive; audit có một bộ lọc event. Không trả totalCount bằng cách quét collection.

## Upload/download và retry

PUT dùng `Content-Type: application/pdf`, body là byte PDF trực tiếp, **không multipart/form-data**. Server tự sinh đuôi `.pdf`; không nhận tên/path từ client. Giới hạn mặc định 20 MiB, đọc stream vào file tạm và kiểm tra `%PDF-`; không coi kiểm tra chữ ký là xác minh toàn vẹn/quét mã độc. File do admin tin cậy cung cấp. File available không được thay bằng nội dung khác; tạo document mới cho phiên bản PDF khác.

Trạng thái: pending_upload → available hoặc upload_failed; xóa: deletion_pending → deleted. Upload có lease để ngăn request cạnh tranh. Lỗi upload có thể để object đã ghi mà metadata chưa hoàn tất; chờ lease hết hạn (mặc định 15 phút), chạy reconcile rồi retry với version mới. Reconcile hủy upload quá hạn và xóa object của attempt; không tự công bố file chưa hoàn tất.

Download tải object theo generation cố định vào file tạm có giới hạn dung lượng, trả attachment rồi dọn file. Quyền được kiểm tra khi bắt đầu request; luồng download đang chạy không bị cắt khi admin khóa tài khoản sau đó. Object Storage thiếu trả lỗi provider 503 để operator điều tra.

Xóa ẩn dữ liệu trước khi xóa object. 503 không có nghĩa dữ liệu vẫn hiển thị: GET admin để xem trạng thái, sau đó retry hoặc reconcile. Document tombstone được giữ, không xóa metadata và audit.

## Lỗi

```json
{"error": {"code": "version_conflict", "message": "Resource changed; reload before retrying"}, "requestId": "trace-id"}
```

401: token thiếu/sai/hết hạn/thu hồi; 403: thiếu quyền/profile hoặc bị khóa; 404: không tồn tại/chưa public/đã xóa; 409: xung đột version/file/upload; 413: quá giới hạn; 415: sai MIME/chữ ký; 422: input/query/cursor sai; 428: thiếu If-Match; 429: gateway giới hạn tốc độ; 503: dependency lỗi. Lỗi bất ngờ trả 500 không kèm stack trace. Dùng X-Request-ID để đối chiếu log; request ID client chỉ chấp nhận ký tự an toàn tối đa 64 ký tự.
