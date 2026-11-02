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

## AI settings

Thiết lập có đăng nhập tài khoản dự án qua Firebase Email/Password, cấu hình API key cá nhân và key chung (admin), chọn OpenAI/Claude, nguồn key và cách tra cứu. Cấu hình NEXT_PUBLIC_FIREBASE_API_KEY và NEXT_PUBLIC_API_URL theo `.env.example`; không đặt API key AI ở frontend env. Phiên chỉ ở bộ nhớ và cần đăng nhập lại khi tải lại trang. Xem [AI connections](../../docs/ai-connections.md). Các thao tác thư viện demo vẫn local; hỏi đáp sau đăng nhập gọi backend RAG với option đã chọn. OAuth subscription chỉ hiển thị trạng thái hỗ trợ, chưa có login hosted được bật.

Lối vào tài khoản luôn hiện ở góc phải header: **Đăng nhập** khi chưa có phiên, **Tài khoản** khi đã đăng nhập. **Kết nối AI** nằm ở header và sidebar; trên mobile nút ở header hiển thị **AI**. Bấm đăng nhập sẽ đưa tới form và focus email. Màn Hỏi đáp có lời nhắc kết nối khi chưa đăng nhập.
