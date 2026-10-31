# Backend implementation verification

Ngày xác minh: 2026-11-01. Phạm vi theo backend-plan/API contract, không lấy tiến độ issue làm tiêu chí. Không triển khai tính năng LLM/AI.

## Kết quả

| Kiểm tra | Kết quả |
|---|---|
| Ruff lint và format | Đạt |
| Python compileall | Đạt |
| Git diff whitespace check | Đạt |
| Domain/API/CLI tests trong image Python 3.11 | 26 passed |
| Integration tests trên Auth, Firestore, Storage Emulator | 7 passed |
| Chạy chung toàn bộ tests trong container + emulator | **33 passed** |
| Docker build image backend non-root | Đạt, image local `legal-api-backend:verify` |
| Docker Compose config | Đạt |
| Nginx `nginx -t` trong container thật | Đạt |
| Gateway smoke qua hai container/network tạm | Đạt: health 200, thiếu token 401, quá dung lượng 413 + CORS, burst 429 + Retry-After, access log không chứa query |

Bộ test container dùng dependencies được resolver cài từ requirements, gồm FastAPI 0.162.0, Starlette 1.10.0, Firebase Admin 6.9.0, Firestore client 2.34.1 và Storage client 3.17.1. Có một cảnh báo deprecation từ TestClient/httpx; không có test fail. Đây là các phiên bản được kiểm tra trong lần build này, không phải lockfile dependencies.

Các trường hợp đã xác minh: bootstrap idempotent/không tin role token; khóa profile và Firebase identity; token sai/hết hạn/thu hồi; allowlist request/response; version conflict; upload stream giới hạn dung lượng và chữ ký; retry upload cùng checksum; lỗi Storage hoặc lỗi commit metadata sau upload; upload cạnh tranh; xóa dở và retry; đối soát lease/file mồ côi; phân trang trùng khóa và cursor giữ nanosecond; toàn bộ query mode; audit; CLI dry-run/project guard; rules chặn client đọc/ghi trực tiếp.

Integration tests chỉ dùng `demo-legal-api`, host loopback, identity và PDF giả. Không dùng project production, không gửi nội dung tới LLM. Container/network smoke test và emulators đã dừng sau khi chạy.

## Tái chạy

Theo [backend quickstart](../apps/api/README.md) để cài prerequisites và chạy lint/unit/integration. CI đã cấu hình hai job: test (gồm emulator) và container build/config/import. Chưa có lần chạy GitHub Actions được kích hoạt từ phiên làm việc này.

Image build:

```bash
docker build -t legal-api-backend:verify -f infra/docker/Dockerfile.api apps/api
```

## Giới hạn trước phát hành

Chưa tạo/cấu hình hoặc deploy tài nguyên cloud; chưa smoke test IAM/index trên Firebase dev thật; chưa bật backup/PITR/Storage retention hoặc diễn tập restore. Emulator không xác minh đầy đủ IAM và yêu cầu composite indexes của Firestore thật. Các bước này có hướng dẫn trong [runbook](backend-operations.md) và phải hoàn tất theo môi trường phát hành.
