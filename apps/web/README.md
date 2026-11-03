# Legal AI — HTML, CSS, JavaScript thuần

Giao diện nối với backend FastAPI của dự án, không cần build.

- `index.html`: bố cục, trang, form và hộp thoại.
- `style.css`: font, màu sắc và responsive.
- `api.js`: gọi backend (cookie phiên, CSRF, thông báo lỗi tiếng Việt).
- `script.js`: đăng nhập, kho tài liệu, hỏi đáp, trích dẫn và thiết lập.

## Chạy

1. Chạy backend (xem `apps/api/README.md`), mặc định http://127.0.0.1:8000. Worker xử lý PDF chạy riêng: `python -m app.workers.ingestion`.
2. Chạy giao diện từ thư mục gốc repo:

```powershell
python -m http.server 8085 --bind 127.0.0.1 --directory apps/web
```

Mở http://127.0.0.1:8085. Backend đã cho phép origin cổng 8085 (`BACKEND_CORS_ORIGINS`). Dùng đúng `127.0.0.1` ở cả hai bên để cookie phiên được gửi kèm.

Nếu terminal đã ở trong `apps/web`, không thêm `--directory apps/web` vì đường dẫn đó sẽ
được tính tiếp từ thư mục hiện tại. Chạy:

```bash
python -m http.server 8085 --bind 127.0.0.1
```

Nếu server cũ đang chiếm cổng 8085, nhấn `Ctrl+C` trong terminal chạy server đó trước khi chạy
lại. Lỗi 404 cho `favicon.ico` không ảnh hưởng đến trang.

Đổi địa chỉ API ở thẻ `<meta name="api-base">` trong `index.html`. Đăng nhập Google dùng client ID
công khai trả về từ backend khi `GOOGLE_OAUTH_CLIENT_ID` được cấu hình; thẻ
`<meta name="google-client-id">` có thể dùng để ghi đè. Đăng ký origin
`http://127.0.0.1:8085` trong Authorized JavaScript origins của đúng OAuth client.

## Chức năng

- Chế độ khách, đăng ký, đăng nhập Google/email, xem và thu hồi phiên đăng nhập.
- Thư viện: chọn kho dùng chung hoặc kho riêng; thêm PDF, xem trạng thái xử lý nền, xử lý lại, xóa, đọc PDF. Quản trị viên thêm văn bản dùng chung và xuất bản bản dựng mới.
- Hỏi đáp: chọn tối đa 5 kho, mốc thời gian và nhà cung cấp AI; câu trả lời có trạng thái, giả định, câu hỏi cần bổ sung, giới hạn nguồn và trích dẫn bấm được để xem đúng đoạn nguồn.
- Thiết lập: khóa API cá nhân hoặc dùng chung (admin), OpenCode local và ChatGPT Plus/Pro
  OAuth local, tài khoản và xóa dữ liệu trên thiết bị. Provider/model/nguồn key và cách tra cứu
  được chọn trong phần hỏi đáp. OAuth local không tự chuyển sang API key khi mất phiên.

Lịch sử hội thoại và đánh dấu chỉ lưu trong localStorage, tách theo tài khoản và bị xóa khi đăng xuất. Khóa API và token không bao giờ nằm trong localStorage.

ChatGPT OAuth cần `OPENCODE_LOCAL_ENABLED=true` và `OPENCODE_CHATGPT_LOCAL_ENABLED=true`,
Docker và OpenCode theo [hướng dẫn API](../../docs/ai-connections.md#thử-chatgpt-oauth-local).
Phiên chỉ dành cho thử nghiệm local. Với chế độ này, RAG tra theo số hiệu/điều; để dùng tìm kiếm
ngữ nghĩa và xử lý PDF cần một nhà cung cấp embedding do backend cấu hình. Với OpenRouter, key
embedding dùng chung được cấu hình ở backend và tách biệt khỏi key/model trả lời. Model NVIDIA
miễn phí không nhận nội dung mật hoặc dữ liệu cá nhân; xác nhận điều kiện tại form trước khi gửi.

Bản Next.js cũ vẫn còn trong `src/` để tham khảo, nhưng không được tải bởi bản HTML này.
