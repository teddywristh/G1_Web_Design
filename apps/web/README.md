# Lề Luật — frontend

Next.js App Router + React + TypeScript + CSS + Lucide. Node.js 20.9+.

## Chạy từ thư mục gốc repo (PowerShell)

```powershell
cd apps/web
npm.cmd install
npm.cmd run dev
```

Mở http://127.0.0.1:3000. Dùng npm.cmd để tránh chặn npm.ps1 trên Windows.

## Kiểm tra

```powershell
npm.cmd run typecheck
npm.cmd run build
npm.cmd start
```

## Chức năng

- Tìm tên/số hiệu/cơ quan, lọc loại, sắp xếp, đánh dấu và xóa tài liệu.
- Thêm PDF: kiểm tra đuôi, MIME, chữ ký PDF, tối đa 20 MB. Đọc bằng trình đọc PDF của trình duyệt và tải file.
- Tạo/xóa nghiên cứu, đổi tên, lưu câu hỏi và ghi chép. Chưa có câu trả lời AI.
- Thiết lập, kiểm tra backend, khôi phục dữ liệu mẫu.
- Responsive, keyboard focus, native modal dialog.

Đây là bản trải nghiệm local, chưa có đăng nhập hoặc quyền Admin thực tế. Metadata và ghi chép lưu trong localStorage. PDF dùng object URL, chỉ giữ trong phiên; tải lại trang cần chọn lại PDF. Các bản ghi mẫu chỉ minh họa giao diện, không xác nhận hiệu lực pháp lý và không chứa PDF gốc.

Backend hiện chỉ có /health. Route Next.js /api/health gọi endpoint này phía server, không cần CORS. Đặt API_URL=http://127.0.0.1:8000 trong .env.local nếu cần; đây cũng là mặc định. Không cần bật backend để xem FE. Chưa gọi API CRUD hoặc Firebase do chưa có route nghiệp vụ.

Giao diện mở vào trang hỏi đáp, có câu hỏi gợi ý, lịch sử và phím Enter để lưu câu hỏi (Shift + Enter xuống dòng). AI chưa được kết nối nên không sinh câu trả lời mẫu.

Font hệ thống Segoe UI/Arial hỗ trợ tiếng Việt, không tải Google Fonts. Giao diện dùng CSS thuần, giảm trang trí và ưu tiên khả năng đọc.

Source: src/app/page.tsx (UI và tương tác), src/app/globals.css (design và responsive), src/lib/workspace.ts (types, metadata mẫu, helpers).
