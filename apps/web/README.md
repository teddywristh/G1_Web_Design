# Legal AI — HTML, CSS, JavaScript thuần

Giao diện nối với backend FastAPI của dự án, không cần build.

## Cấu trúc frontend

```text
apps/web/
├── index.html
├── html/
│   ├── auth.html
│   ├── sidebar.html
│   ├── header.html
│   ├── chat.html
│   ├── library.html
│   ├── settings.html
│   ├── footer.html
│   ├── upload.html
│   ├── document.html
│   └── evidence.html
├── css/
│   ├── main.css
│   ├── base.css
│   ├── layout.css
│   ├── chat.css
│   ├── library.css
│   ├── dialogs.css
│   ├── responsive.css
│   ├── auth.css
│   ├── retrieval.css
│   ├── settings.css
│   └── theme.css
└── js/
    ├── main.js
    ├── app.js
    ├── core.js
    ├── api.js
    ├── auth.js
    ├── navigation.js
    ├── knowledge-bases.js
    ├── documents.js
    ├── upload.js
    ├── chat.js
    ├── evidence.js
    ├── settings.js
    └── sessions.js
```

`index.html` giữ cấu hình API, font/CSS và vị trí các phần giao diện. `js/main.js` tải các tệp HTML cố định, ghép vào trang rồi mới nạp `js/app.js` để gắn sự kiện và khởi tạo phiên. Các tệp HTML con là nội dung được ghép, không phải các trang mở riêng.

`css/main.css` khai báo thứ tự tải CSS. `base.css` chứa biến màu và thành phần dùng chung; `layout.css` là khung trang; `responsive.css` là bố cục màn hình nhỏ. `retrieval.css` định dạng lựa chọn nguồn và trích dẫn. `theme.css` giữ các điều chỉnh giao diện cuối cùng; thứ tự nạp được giữ như trước để bảo toàn cascade.

JavaScript dùng ES modules: hàm dùng giữa các file được khai báo bằng `import/export`. `core.js` chứa state, nhãn trạng thái, helper DOM và lưu trữ trên trình duyệt. `api.js` phụ trách HTTP, cookie phiên, CSRF và lỗi API. `app.js` nối các thao tác chung như menu, chuyển trang và xóa dữ liệu local. Các module chức năng còn lại quản lý sự kiện của phần mình.

## Tìm code theo chức năng

| Phần cần trình bày                         | HTML                                      | JavaScript                      | CSS chính                              |
| ------------------------------------------ | ----------------------------------------- | ------------------------------- | -------------------------------------- |
| Đăng nhập, đăng ký, Google                 | `html/auth.html`                          | `js/auth.js`                    | `css/auth.css`                         |
| Điều hướng, menu mobile                    | `html/sidebar.html`, `html/header.html`   | `js/navigation.js`, `js/app.js` | `css/layout.css`, `css/responsive.css` |
| Kho riêng, kho chung, xuất bản             | `html/library.html`                       | `js/knowledge-bases.js`         | `css/library.css`                      |
| Danh sách, tìm kiếm, đánh dấu, đọc/xóa PDF | `html/library.html`, `html/document.html` | `js/documents.js`               | `css/library.css`, `css/dialogs.css`   |
| Chọn file và tải PDF                       | `html/upload.html`                        | `js/upload.js`                  | `css/dialogs.css`                      |
| Câu hỏi, lịch sử, câu trả lời              | `html/chat.html`                          | `js/chat.js`                    | `css/chat.css`, `css/retrieval.css`    |
| Mở đoạn nguồn của trích dẫn                | `html/evidence.html`                      | `js/evidence.js`                | `css/retrieval.css`, `css/dialogs.css` |
| Khóa API, ChatGPT local                    | `html/settings.html`                      | `js/settings.js`                | `css/settings.css`                     |
| Danh sách và thu hồi phiên                 | `html/settings.html`                      | `js/sessions.js`                | `css/settings.css`                     |

Khi giải thích một thao tác, bắt đầu từ ID của nút/form trong HTML, tìm ID đó trong module JS tương ứng, rồi theo lệnh `api.get/post/put/del` tới backend. Ví dụ: `#question-form` trong `html/chat.html` → listener submit và `requestBody()` trong `js/chat.js` → `api.post("/rag/ask", ...)` trong `js/api.js`.

## Chạy

Chỉ xem giao diện thì cần Python 3 và trình duyệt, không cần npm install/build. Từ **gốc repo**:

```powershell
python -m http.server 8085 --bind 127.0.0.1 --directory apps/web
```

Mở http://127.0.0.1:8085. Khi chưa chạy API, trang dùng chế độ khách. Để đăng nhập, quản lý PDF và hỏi đáp, chạy emulator, API, worker và embedding theo [hướng dẫn ở README gốc](../../README.md#quickstart--local-development). Backend mặc định ở http://127.0.0.1:8000; mẫu cấu hình cho phép origin cổng 8085 (`BACKEND_CORS_ORIGINS`). Dùng `127.0.0.1` ở cả hai bên để cookie phiên được gửi kèm.

Không mở bằng `file://` hoặc mở riêng các file trong `html/`. `js/main.js` cần HTTP để Fetch các phần HTML rồi mới khởi tạo module.

Nếu terminal đã ở trong `apps/web`, không thêm `--directory apps/web` vì đường dẫn đó sẽ
được tính tiếp từ thư mục hiện tại. Chạy:

```powershell
python -m http.server 8085 --bind 127.0.0.1
```

Hoặc tại `apps/web`, dùng `npm.cmd run dev` / `npm.cmd start` trong PowerShell: cả hai chạy cùng static server trên cổng 8085, không chạy Next.js. Hậu tố `.cmd` tránh lỗi chặn `npm.ps1`; trên macOS/Linux dùng `npm`. Chọn một cách để tránh trùng cổng. Các npm script `dev:legacy`, `build:legacy`, `start:legacy`, `typecheck:legacy` chỉ dành cho bản Next.js tham khảo và cần cài dependencies nếu sử dụng.

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

Bản Next.js cũ vẫn còn trong `src/` để tham khảo, cùng các tệp cấu hình npm/TypeScript. Chúng không được tải bởi bản HTML này. Các thư mục `html/`, `css/`, `js/` là mã nguồn của frontend hiện tại; không đặt bản sao dự phòng hoặc file thử nghiệm trong đó.

## Embedding local (Nemotron)

Backend và worker dùng `EMBEDDING_PROVIDER=local`, endpoint nội bộ
`http://127.0.0.1:8010`. Không cần key OpenRouter cho upload/tìm kiếm ngữ nghĩa.
Mẫu `apps/api/.env.example` chọn profile này; file `.env` đã có phải được kiểm tra riêng. Khởi động embedding host và đợi `/ready` trả 200. Trên PowerShell, chạy các terminal theo README gốc. Script `bash scripts/local-embed-demo.sh` là lựa chọn cho Bash/WSL khi emulator và embedding host đã sẵn sàng, không phải lệnh PowerShell.
Mở http://127.0.0.1:8085, đăng nhập, tạo kho riêng mới và tải PDF. Khi trạng thái
Sẵn sàng, chọn kho đó trong Hỏi đáp và chế độ hybrid. Model trả lời vẫn cần API key
hoặc phiên ChatGPT được kết nối trong Thiết lập. Xem
[hướng dẫn embedding](../embedding/README.md).

## Kiểm tra mã nguồn

Từ gốc repo, PowerShell với Node.js 22+:

```powershell
Get-ChildItem apps/web/js/*.js | ForEach-Object {
  Get-Content -Raw $_.FullName | node --input-type=module --check
}
```

Kiểm tra thêm bằng trình duyệt: tải trang, chuyển Hỏi đáp/Thư viện/Thiết lập, thử desktop/mobile và xem Console/Network. Kiểm tra cú pháp không xác nhận kết nối Firebase, cookie, provider hoặc chất lượng trả lời AI.
