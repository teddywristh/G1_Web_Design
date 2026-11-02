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

Thư viện và ghi chép trong giao diện vẫn là dữ liệu local; đăng nhập và quyền Admin do backend quản lý. Metadata và ghi chép lưu trong localStorage. PDF dùng object URL, chỉ giữ trong phiên; tải lại trang cần chọn lại PDF. Các bản ghi mẫu chỉ minh họa giao diện, không xác nhận hiệu lực pháp lý và không chứa PDF gốc.

Route Next.js /api/health gọi health endpoint phía server. Cấu hình NEXT_PUBLIC_API_URL để trình duyệt gọi backend và bật CORS theo origin frontend.

Giao diện mở vào trang hỏi đáp, có câu hỏi gợi ý, lịch sử và phím Enter để lưu câu hỏi (Shift + Enter xuống dòng). Hỏi đáp dùng backend RAG khi đã đăng nhập và cấu hình AI.

Font hệ thống Segoe UI/Arial hỗ trợ tiếng Việt, không tải Google Fonts. Giao diện dùng CSS thuần, giảm trang trí và ưu tiên khả năng đọc.

Source: src/app/page.tsx (UI và tương tác), src/app/globals.css (design và responsive), src/lib/workspace.ts (types, metadata mẫu, helpers).

## AI settings

Thiết lập có đăng ký, đăng nhập email/mật khẩu và Google Sign-In, cấu hình API key cá nhân và key chung (admin), chọn OpenAI/Claude, nguồn key và cách tra cứu. Cấu hình NEXT_PUBLIC_API_URL và NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID theo `.env.example`; không đặt API key AI ở frontend env. Phiên lưu bằng cookie HttpOnly và được khôi phục khi tải lại trang. Xem [AI connections](../../docs/ai-connections.md). Các thao tác thư viện demo vẫn local; hỏi đáp sau đăng nhập gọi backend RAG với option đã chọn. OAuth subscription chỉ hiển thị trạng thái hỗ trợ, chưa có login hosted được bật.

Lối vào tài khoản luôn hiện ở góc phải header: **Đăng ký** và **Đăng nhập** khi chưa có phiên, **Tài khoản** khi đã đăng nhập. **Kết nối AI** nằm ở header và sidebar; trên mobile nút ở header hiển thị **AI**. Bấm đăng nhập sẽ đưa tới form và focus email. Màn Hỏi đáp có lời nhắc kết nối khi chưa đăng nhập.

Cách cấu hình Google, cookie, Firebase và quản lý phiên: [Kế hoạch xác thực](../../docs/auth-plan.md).
