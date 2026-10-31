# Backend operations runbook

## Môi trường và khởi động

Xem `apps/api/README.md` cho chạy local. Cấu hình mặc định là project `demo-legal-api` với ba emulator, không cần service account. Dev thật và production dùng project riêng; tuyệt đối không dùng production cho test. Firebase init dùng chung cho API, CLI và helper Storage cũ.

Các biến ở `apps/api/.env.example`: APP_ENV, APP_NAME, FIREBASE_PROJECT_ID, FIREBASE_STORAGE_BUCKET, GOOGLE_APPLICATION_CREDENTIALS (local thật nếu cần), ba emulator host, BACKEND_CORS_ORIGINS (JSON array), MAX_UPLOAD_SIZE_BYTES (20 MiB), STORAGE_TIMEOUT_SECONDS (30), UPLOAD_LEASE_SECONDS (900), ORPHAN_GRACE_SECONDS (3600). Lease tối thiểu 300 giây, lớn hơn timeout ghi object; dọn orphan chỉ sau ít nhất 1800 giây. Production đặt APP_ENV=production, xóa cả ba emulator host và không dùng project demo. Ứng dụng từ chối khởi động với cấu hình production/emulator hoặc CORS `*`.

Docker local:

```bash
cp apps/api/.env.example apps/api/.env
firebase --config firebase.docker.json emulators:start --project demo-legal-api --only auth,firestore,storage
# Terminal khác:
docker compose -f infra/docker/docker-compose.yml up --build
```

API qua gateway tại http://localhost:8001. Container dùng host.docker.internal, extra_hosts hỗ trợ Linux; emulator phải bind địa chỉ mà container truy cập được. Cấu hình mặc định Firebase bind loopback phù hợp chạy API trên host. Cấu hình `firebase.docker.json` bind `0.0.0.0` để container truy cập host; chỉ dùng trên máy/mạng phát triển tin cậy và chặn truy cập từ mạng ngoài bằng firewall. Cấu hình mặc định `firebase.json` vẫn chỉ bind loopback. UI không cần bật.

Gateway `infra/nginx/api.conf` thực thi 120 request/phút/IP, burst 30 và tối đa 5 kết nối/IP, trả 429 với Retry-After. Một gateway chia sẻ rate zone giữa các backend replica; nếu nhân nhiều gateway phải dùng edge limiter tập trung. IP là peer thật; khi sau load balancer chỉ cấu hình real_ip cho dải IP proxy tin cậy. Không mở cổng backend ra ngoài để bypass gateway. Đồng bộ giới hạn 20m ở gateway khi đổi MAX_UPLOAD_SIZE_BYTES. Local HTTP; production bắt buộc TLS ở ingress. Cập nhật map allowed_origin trong gateway theo origin frontend khi triển khai để response lỗi ở edge có CORS phù hợp.

## Cấp admin

Người dùng đăng nhập và bootstrap trước. UID lấy từ Firebase Auth, không lấy UID do request không xác thực cung cấp. CLI kiểm tra identity Firebase còn tồn tại/không disabled và profile còn active. Không có public API cấp role.

```bash
python scripts/backend_admin.py --project demo-legal-api grant-admin --uid USER_UID
python scripts/backend_admin.py --project demo-legal-api --apply grant-admin --uid USER_UID
```

Lệnh đầu dry-run; lệnh có `--apply` mới ghi và tạo audit trong cùng transaction. `--project` bắt buộc khớp runtime. Production vận hành bằng identity riêng có quyền quản trị, không công khai CLI thành HTTP endpoint.

Khóa user qua API chỉ sửa `isActive` trong Firestore; backend từ chối request mới ngay cả khi ID token chưa hết hạn. Firebase Auth disabled/revoked được kiểm tra riêng mỗi request. Không thu hồi luồng download đã bắt đầu. Không cho admin sửa active của chính mình; các thao tác khôi phục admin do operator có quyền thực hiện trực tiếp có ghi nhận vận hành.

## Đối soát Storage/Firestore

Upload claim lease → ghi object duy nhất → transaction công bố file. Một transaction Firestore không thể bao gồm Storage. Khi request lỗi, GET admin để biết version/trạng thái thực tế; không tự giả định thao tác chưa chạy.

```bash
python scripts/backend_admin.py --project demo-legal-api reconcile
python scripts/backend_admin.py --project demo-legal-api --apply reconcile
```

Dry-run trả số expiredUploads, pendingDeletions, orphanFiles và errors. Apply dùng transaction để hủy lease quá hạn trước khi dọn object. Upload đang có lease còn hạn được giữ. Xóa dở được tiếp tục theo object generation; object đã mất được coi là xóa thành công. Orphan chỉ thuộc prefix `legal-documents/{id}/{attempt}.pdf`, đủ tuổi grace và không còn được metadata/lease tham chiếu. File ngoài prefix không bị đụng đến.

Lịch vận hành khuyến nghị: chạy dry-run khi điều tra; chạy apply mỗi 15 phút bằng một scheduler/job có cấu hình project tường minh, concurrency 1. CLI trả exit code 1 nếu có lỗi riêng lẻ; giám sát exit code và thống kê. Tránh nhiều operator/job đối soát đồng thời; version/generation vẫn ngăn ghi đè nhưng có thể tạo lỗi cần retry. Dữ liệu lớn được duyệt từng trang; không tải cả collection/bucket vào RAM.

## Triển khai và quyền runtime

1. Tạo project dev và production riêng. Bật Firebase Authentication và provider cần dùng, Firestore, bucket riêng tư.
2. Review và deploy deny-all Firestore/Storage rules và indexes bằng Firebase CLI với `--project` cụ thể. Chờ tất cả index build xong trên dev trước smoke test; emulator không thực thi yêu cầu composite index.
3. Build image từ Dockerfile API, chạy non-root. Cấu hình runtime service account qua ADC/Workload Identity; không đóng gói JSON key trong image hoặc frontend.
4. Runtime cần quyền đọc/ghi Firestore, Firebase Auth đọc user phục vụ check_revoked, Storage object create/get/delete/list (liệt kê tối đa 1 object phục vụ readiness). Dùng role/custom role ở đúng project/bucket, không dùng Owner/Editor. Identity deploy có quyền khác identity runtime.
5. Cloud Run hoặc container platform nhận PORT 8000 (cấu hình platform tương ứng); gắn ingress có TLS và giới hạn tốc độ. Nếu Cloud Run dùng load balancer/Cloud Armor, chỉ cho ingress qua load balancer và xác nhận limiter bằng kiểm thử 429. Gateway Nginx trong repo là phương án cho triển khai container; không tự cấu hình cloud trong lần triển khai code này.
6. Cấu hình CORS đúng origin frontend. Khởi động probe `/health`; readiness `/ready` đọc Firestore và kiểm tra liệt kê object trong bucket với timeout 2 giây/dependency. Response không lộ project, host hoặc credentials.
7. Smoke test trên dev thật: tạo user → bootstrap → CLI cấp admin → tạo metadata → upload → user tra cứu/tải → sửa với version → khóa user → kiểm tra 403 → xóa và kiểm tra audit. Thử mọi query mode để xác nhận indexes và IAM.
8. Chỉ chuyển traffic production sau khi smoke test dev đạt; giữ revision trước để rollback. Không tự deploy cloud hoặc dùng credentials production khi chạy bộ test repository.

## Log, quota và tài nguyên

Backend ghi JSON event HTTP gồm route template, method, status, durationMs và requestId; không ghi query, body, email, bearer token hoặc nội dung PDF. Provider/unhandled errors chỉ ghi loại exception, không trả stack trace. Gateway trong repo dùng JSON access log gồm method, `$uri` (không query string), status và request ID; không thêm query string hoặc Authorization vào log format.

Audit mutation thành công được commit nguyên tử với dữ liệu, upload_failed/upload_expired có result failed; callback retry không tạo duplicate audit. Các request bị từ chối trước mutation được ghi trong HTTP log, không tạo Firestore audit. Giới hạn quyền sửa/xóa audit cho operator, frontend không truy cập trực tiếp.

Theo dõi tỷ lệ 5xx/429, latency, request đang chạy, dung lượng file tạm, Firestore read/write quota, Storage quota và số lease/xóa dở. Thiết lập alert theo tải dev thực tế trước release. Download spool vào file tạm và dọn sau response, tối đa 20 MiB/file; trên Cloud Run `/tmp` tiêu thụ memory, đặt concurrency và memory phù hợp. Không tăng replica/concurrency mà bỏ qua giới hạn tài nguyên. Dừng tiến trình đột ngột có thể để file tạm; container restart dọn ephemeral filesystem.

## Backup, restore và rollback

Trước production, bật Firestore backup/PITR phù hợp gói dịch vụ và Storage soft delete/versioning theo chính sách dự án, xác định retention và chi phí. Backup metadata và object cần mốc thời gian tương ứng; không coi backup Firestore là backup PDF. Định nghĩa retention riêng cho audit trước khi cấu hình TTL, không mặc định xóa log.

Diễn tập trên project dev tách biệt: tạo bộ dữ liệu/PDF mẫu → backup/export → xóa mẫu → restore Firestore và object đúng generation → kiểm tra quyền, metadata, SHA-256 và download → chạy reconcile dry-run để phát hiện lệch → ghi lại thời gian khôi phục, RPO/RTO và bằng chứng. Không chạy reconcile apply trên dữ liệu vừa restore trước khi xác minh đầy đủ tham chiếu file.

Rollback API bằng revision/image trước, kiểm tra `/ready` và luồng đọc. Thay đổi schema triển khai theo hướng thêm trường; không xóa field/collection cũ. Nếu có dữ liệu scaffold cũ: kiểm kê trước rollout; profile cần version/updatedAt/isActive/role, văn bản cần đủ schema, normalizedTitle/normalizedNumber/deletedAt/fileState/version. Không tự đánh dấu file cũ available hoặc suy diễn trạng thái hiệu lực; chuẩn hóa và kiểm tra thủ công trên dev, backup rồi mới migrate production. Các collection hội thoại và trường xử lý ngoài phạm vi không bị sửa bởi backend này.
