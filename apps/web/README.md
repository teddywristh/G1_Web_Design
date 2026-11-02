# Legal AI — HTML, CSS, JavaScript thuần

Chỉ có 3 file nguồn:

- `index.html`: bố cục, các trang, form và cửa sổ PDF.
- `style.css`: font, màu sắc và responsive.
- `script.js`: sự kiện, hỏi đáp, thư viện, PDF và localStorage.

## Chạy từ thư mục gốc repo

```powershell
python -m http.server 5500 --bind 127.0.0.1 --directory apps/web
```

Mở http://127.0.0.1:5500. Không cần npm, React hay bước build. Có thể dùng VS Code Live Server với `index.html`.

## Chức năng

- Hỏi đáp: câu hỏi gợi ý, tạo/xóa/đổi tên cuộc trò chuyện, lưu lịch sử. Enter để lưu, Shift + Enter xuống dòng.
- Thư viện: tìm tên/số hiệu/cơ quan, lọc loại, sắp xếp, đánh dấu, xóa.
- PDF: kiểm tra đuôi, MIME, chữ ký PDF và giới hạn 20 MB; đọc và tải file trong phiên.
- Thiết lập: khôi phục dữ liệu mẫu.

Metadata, đánh dấu và câu hỏi lưu trên trình duyệt bằng localStorage. PDF chỉ giữ trong phiên; tải lại trang cần chọn lại file. Dùng cùng địa chỉ và cổng để truy cập dữ liệu đã lưu của phiên bản trước.

Đây là bản trải nghiệm, chưa đăng nhập Firebase, chưa gọi API nghiệp vụ và chưa tạo câu trả lời AI. Các bản ghi mẫu không đính kèm PDF gốc hoặc xác nhận hiệu lực pháp lý. Font Segoe UI/Arial hỗ trợ tiếng Việt và không cần tải font từ mạng.
