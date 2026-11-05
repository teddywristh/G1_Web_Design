# Kiểm tra giao diện và hỏi đáp tài liệu

Giao diện HTML dùng tông đỏ trầm, nền sáng; CSS nằm trong `apps/web/css`, xử lý giao diện trong `apps/web/js`, các phần HTML trong `apps/web/html`.

Trạng thái hệ thống xuất hiện khi API đang chạy, phân biệt xác thực, gửi OTP, truyền PDF và tra cứu. Tiến trình chat hiện ngay sau khi gửi câu hỏi. Đây là trạng thái yêu cầu thực tế, không phải nội dung suy luận nội bộ của AI.

## Demo trên PDF

Tải một PDF qua Thư viện tài liệu, chờ Sẵn sàng tra cứu, chọn model rồi hỏi một câu có nội dung rõ ràng trong tài liệu. Mở số nguồn trong câu trả lời để đối chiếu đoạn trích và PDF bên phải.

Ví dụ tài liệu kiểm thử chứa:

> Điều 2. Thời gian đào tạo
> 1. Thời gian đào tạo ban đầu tối đa là 12 ngày.

Câu hỏi: “Theo Điều 2, thời gian đào tạo ban đầu tối đa bao nhiêu ngày?”

Kết quả mong đợi: trả lời 12 ngày và có nguồn Điều 2, Khoản 1, trang 1. Đây là dữ liệu giả định để kiểm thử, không phải quy định pháp luật.

Đã chạy demo cục bộ với PDF thật qua bước đọc PDF, xử lý nền, truy xuất, kiểm tra trích dẫn và mở nguồn. Repository, embedding và câu trả lời model dùng adapter kiểm thử; chưa xác nhận dịch vụ AI cloud hoặc email Gmail thực tế. Không đưa adapter kiểm thử vào frontend sản phẩm.

## Trích xuất văn bản

Bộ đọc nối các dòng mềm trong cùng đoạn, giữ ranh giới điều khoản và chuẩn hóa Unicode. Bộ chia đoạn ưu tiên kết thúc câu hoặc khoảng trắng, tránh cắt giữa từ. Tài liệu đã xử lý trước đây cần xử lý lại để áp dụng parser/chunker mới; đổi CSS không tự sửa dữ liệu cũ. OCR nhận sai ký tự vẫn cần kiểm tra đối chiếu PDF.

## Chạy kiểm tra

Từ gốc repo:

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_auth.py apps/api/tests/test_rag.py apps/api/tests/test_local_ocr.py apps/api/tests/test_knowledge_flow.py apps/api/tests/test_local_storage.py -q
python -m http.server 8085 --bind 127.0.0.1 --directory apps/web
```

Mở `http://127.0.0.1:8085`. API và ingestion worker chạy theo README chính. Màn hình tự động trên Chrome được kiểm tra ở kích thước desktop và mobile, với API giả lập để kiểm tra trạng thái chờ, lỗi email trùng, OTP, đăng nhập, đăng xuất và mở nguồn.
