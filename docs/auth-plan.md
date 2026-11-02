# Kế hoạch triển khai xác thực

1. Đăng ký/đăng nhập email: FastAPI quản lý mật khẩu mới bằng bcrypt, giữ Firebase UID và profile hiện có; ID token Firebase cũ vẫn được backend xác thực. Mật khẩu không bao giờ được lưu hoặc log dạng rõ.
2. Google Sign-In: trình duyệt dùng nút Google chính thức, backend xác minh chữ ký, issuer, audience, expiry và email trước khi tạo phiên. Liên kết tài khoản email đã có mật khẩu yêu cầu đăng nhập tài khoản đó trước.
3. Session: token ngẫu nhiên trong cookie HttpOnly, chỉ lưu hash server-side; có hạn, CSRF token, danh sách phiên, thu hồi phiên hiện tại/từng phiên/tất cả phiên. Giữ Authorization Bearer cho client Firebase hiện tại.
4. UI: đăng ký, đăng nhập, Google, đăng xuất và quản lý phiên; cấu hình CORS/cookie theo môi trường. Không xây thêm hệ thống gửi OTP vì Google Sign-In là phương án xác thực người dùng đã chọn.
5. Kiểm tra: unit/API cho mật khẩu, phân quyền, CSRF, cookie/session, Google token và account linking; integration với Firebase Emulator; browser test và build frontend.

## Cấu hình và vận hành

- Tạo OAuth **Web application** client trong Google Cloud, cấu hình consent screen và thêm origin của frontend vào Authorized JavaScript origins (ví dụ `http://localhost:3000` và domain HTTPS của website). Đặt cùng client ID vào `GOOGLE_OAUTH_CLIENT_ID` ở backend và `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID` ở frontend, rồi khởi động/build lại hai ứng dụng. Nút Google không hoạt động khi thiếu cấu hình này.
- Email đã có tài khoản cần đăng nhập trước và bấm liên kết Google trong trang tài khoản. Email Google khác email tài khoản vẫn có thể liên kết nếu chưa thuộc tài khoản khác. Backend xác minh Google ID token và nonce; không tin email do frontend tự gửi.
- Tài khoản đăng ký mới lưu bcrypt hash trong Firestore, không lưu mật khẩu rõ. Tài khoản Firebase Email/Password cũ tiếp tục xác thực với Firebase; đặt `FIREBASE_WEB_API_KEY` ở backend để hỗ trợ các tài khoản đó. Mật khẩu cũ vẫn theo cơ chế lưu của Firebase. Bearer Firebase ID token hiện tại vẫn được hỗ trợ ở API nghiệp vụ.
- Cookie phiên mặc định hết hạn sau 168 giờ (`AUTH_SESSION_HOURS`), là HttpOnly và chỉ lưu hash token ở backend. Các request thay đổi dùng CSRF token. Cấu hình `AUTH_COOKIE_SECURE=true` cho production, dùng HTTPS và liệt kê chính xác frontend origin trong `BACKEND_CORS_ORIGINS`. Ưu tiên frontend và API cùng site; nếu bắt buộc khác site, cần `AUTH_COOKIE_SAMESITE=none` và HTTPS, đồng thời trình duyệt có thể chặn cookie bên thứ ba.
- Đăng xuất thu hồi phiên hiện tại. Danh sách phiên cho phép thu hồi từng phiên; đăng xuất mọi thiết bị vô hiệu hóa toàn bộ phiên ứng dụng và Firebase refresh token. Token đã hết hạn hoặc thu hồi không đăng nhập lại được. Nên thiết lập Firestore TTL cho `auth_sessions.expiresAt` để xóa dữ liệu phiên hết hạn; việc xác thực đã tự kiểm tra hạn ngay cả khi TTL chưa xóa.
- API: `POST /api/v1/auth/register`, `/login`, `/google`, `/logout`, `/logout-all`; `GET /api/v1/auth/google/challenge`, `/me`, `/sessions`; `DELETE /api/v1/auth/sessions/{id}`. Các thao tác có phiên cần header `X-CSRF-Token` cho request thay đổi.
