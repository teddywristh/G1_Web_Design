# Legal AI — HTML, CSS, JavaScript thuần

Bản FE HTML của nhóm gồm 3 file nguồn:

- `index.html`: bố cục, các trang, form và cửa sổ PDF.
- `style.css`: font, màu sắc và responsive.
- `script.js`: sự kiện, hỏi đáp, thư viện, PDF và localStorage.

## Chạy từ thư mục gốc repo

```powershell
python -m http.server 8085 --bind 127.0.0.1 --directory apps/web
```

Mở http://127.0.0.1:8085. Không cần npm, React hay bước build. Có thể dùng VS Code Live Server với `index.html`.

## Chức năng

- Hỏi đáp: câu hỏi gợi ý, tạo/xóa/đổi tên cuộc trò chuyện, lưu lịch sử. Enter để lưu, Shift + Enter xuống dòng.
- Thư viện: tìm tên/số hiệu/cơ quan, lọc loại, sắp xếp, đánh dấu, xóa.
- PDF: kiểm tra đuôi, MIME, chữ ký PDF và giới hạn 20 MB; đọc và tải file trong phiên.
- Thiết lập: khôi phục dữ liệu mẫu.

Metadata, đánh dấu và câu hỏi lưu trên trình duyệt bằng localStorage. PDF chỉ giữ trong phiên; tải lại trang cần chọn lại file. Dùng cùng địa chỉ và cổng để truy cập dữ liệu đã lưu của phiên bản trước.

Đây là bản trải nghiệm, chưa đăng nhập Firebase, chưa gọi API nghiệp vụ và chưa tạo câu trả lời AI. Các bản ghi mẫu không đính kèm PDF gốc hoặc xác nhận hiệu lực pháp lý. Font Segoe UI/Arial hỗ trợ tiếng Việt và không cần tải font từ mạng.

## Code cập nhật từ remote

Backend, RAG và các tính năng tài khoản mới đã được merge từ `origin/main`. Bản HTML vẫn giữ nguyên hành vi local; việc merge Git chưa kết nối các API mới vào `script.js`.

Mã giao diện Next.js từ remote được giữ nguyên trong `src/`, cùng `package.json`, lockfile và cấu hình liên quan, để không mất phần đăng nhập, tài khoản và AI settings mà thành viên khác đã làm. Mã này không được tải khi chạy server HTML ở trên. Muốn chạy riêng bản Next.js: vào `apps/web`, chạy `npm.cmd install` rồi `npm.cmd run dev`; xem `.env.example` và tài liệu trong `docs/` để cấu hình backend.
