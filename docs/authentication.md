# Tài khoản và khôi phục mật khẩu

Email được bỏ khoảng trắng hai đầu và chuyển về chữ thường ở backend. Ví dụ `Minh@gmail.com` và `minh@GMAIL.com` là cùng email. Không tự bỏ dấu chấm hoặc phần sau dấu cộng. Firebase kiểm soát trùng email khi tạo tài khoản, kể cả khi có hai yêu cầu đồng thời.

Tên hiển thị giữ nguyên hoa thường, được phép trùng và không dùng để đăng nhập. Đây chưa phải trường username riêng.

## Gửi OTP qua Gmail

Điền cấu hình trong `apps/api/.env`, sau đó khởi động lại API:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-account@gmail.com
SMTP_PASSWORD=your-google-app-password
SMTP_FROM=your-account@gmail.com
```

Dùng App Password của tài khoản gửi, không dùng mật khẩu đăng nhập Google. Không commit `.env`. SMTP hiện dùng STARTTLS, phù hợp cổng 587. Xem [hướng dẫn Google về App Password](https://support.google.com/accounts/answer/185833).

Từ màn hình đăng nhập, chọn Quên mật khẩu, nhập email, nhận OTP, rồi nhập OTP và mật khẩu mới. Nếu chưa cấu hình SMTP, giao diện thông báo chưa thể gửi; không giả báo gửi thành công.

OTP gồm 6 số, hết hạn sau 10 phút, tối đa 5 lần thử và chỉ dùng một lần. Chờ ít nhất 60 giây để gửi lại. Backend lưu mã băm, không trả OTP trong API. Email không tồn tại vẫn nhận thông báo chung để tránh lộ danh sách tài khoản. Sau khi đổi mật khẩu, phiên đăng nhập cũ bị thu hồi và người dùng đăng nhập lại.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_auth.py -q
```

Kiểm thử tự động dùng dịch vụ email giả lập; việc nhận thư trong Gmail cần kiểm tra bằng cấu hình SMTP thực tế. Trạng thái gửi thành công có nghĩa SMTP đã chấp nhận thư, không bảo đảm thư đã vào hộp thư chính.
