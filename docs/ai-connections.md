# AI connections: key cá nhân, key chung và tính khả thi OAuth

Phạm vi: website có backend dùng chung; hỗ trợ cả credential cá nhân và credential do admin quản lý. Đã triển khai OpenAI/Claude bằng API key. OAuth của tài khoản subscription chưa được bật.

## Khả năng hỗ trợ của nhà cung cấp

| Phương thức | Trạng thái trong website này |
|---|---|
| OpenAI API key | Hoạt động qua key cá nhân, key chung lưu mã hóa hoặc biến môi trường server |
| Anthropic API key | Hoạt động qua key cá nhân, key chung hoặc biến môi trường server |
| ChatGPT Plus/Pro OAuth | Chờ quyền tích hợp hosted; không thể bật chỉ bằng tài khoản Plus của admin |
| Claude Pro OAuth | Không được hỗ trợ cho luồng đăng nhập Claude.ai để ứng dụng bên ngoài gọi model thay người dùng |

Theo [OpenAI Sign in with ChatGPT](https://developers.openai.com/siwc/quickstart), ứng dụng đủ điều kiện có thể sử dụng gói ChatGPT. Tuy nhiên, [hướng tích hợp mở](https://developers.openai.com/siwc/token-sharing-open-source) áp dụng cho OSS/local; website từ xa hoặc có thu phí cần đăng ký quan tâm/quyền truy cập thích hợp. Không coi repo công khai là bằng chứng website hosted đã được duyệt. Đăng nhập định danh đơn thuần không cấp quyền inference bằng gói Plus.

Khi có quyền hosted phù hợp, bước tiếp theo là triển khai theo contract được cấp: OAuth/OIDC + PKCE/state/nonce, callback đã đăng ký, xác minh ID token/scopes, mã hóa access/refresh token, xoay refresh token và thu hồi kết nối. [Luồng plan usage](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference) dùng Responses API với streaming và `store:false`, khác Chat Completions hiện dùng cho key. Vì vậy không thể thay API key hiện tại bằng token lấy từ một app khác.

[Anthropic authentication and credential use](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use) không cho developer cung cấp đăng nhập Claude.ai hoặc trung gian credential subscription cho luồng này. [Claude API authentication](https://platform.claude.com/docs/en/manage-claude/authentication) hỗ trợ API key và các cơ chế workload khác; đây không phải OAuth tiêu dùng quota Claude Pro.

UI và `GET /api/v1/ai/connections` thể hiện hai phương thức OAuth là chưa khả dụng, kèm lý do; không có callback giả hoặc nút báo kết nối thành công khi chưa được hỗ trợ.

## Cấu hình và sử dụng

1. Cài `apps/api/requirements.txt`. Tạo một khóa Fernet bằng `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` và cấu hình `AI_CREDENTIAL_ENCRYPTION_KEY` qua secret manager hoặc environment, dùng cùng khóa trên mọi backend instance.
2. Không ghi khóa mã hóa vào Git. Giữ nó qua restart/deploy; mất khóa thì cần nhập lại các API key. Đổi khóa cần quy trình giải mã/mã hóa lại dữ liệu trước khi loại khóa cũ; phiên bản này chưa có lệnh tự xoay khóa.
3. Frontend HTML không cần biến môi trường. Tài khoản đăng ký ngay trên màn hình đăng nhập; tài khoản Firebase Email/Password cũ cần `FIREBASE_WEB_API_KEY` ở backend. Không đặt API key AI vào HTML/JS.
4. Địa chỉ API đặt ở `<meta name="api-base">` trong `apps/web/index.html`; `BACKEND_CORS_ORIGINS` phải có origin frontend (mặc định gồm cổng 3000 và 8085). Online cần HTTPS.
5. Đăng nhập ở màn hình đầu tiên; khóa AI nằm trong **Thiết lập → Kết nối AI**. Phiên dự án dùng cookie HttpOnly và được khôi phục khi tải lại trang; có thể đăng xuất một hoặc mọi thiết bị trong Thiết lập. Đây là tài khoản dự án, không phải tài khoản ChatGPT/Claude.
6. Có thể cấu hình nhiều kết nối cùng lúc: API key OpenAI, Claude (Anthropic), DeepSeek, OpenRouter (key cá nhân; admin có thêm key chung) và ChatGPT Plus/Pro qua OAuth. API key được nhập một lần, không đọc lại.
7. Trên màn Hỏi đáp chỉ có một ô **Model AI**: combobox gom model theo từng kết nối đã cấu hình, có ô tìm kiếm. Danh sách lấy từ `GET /api/v1/ai/models`: với API key, backend gọi endpoint liệt kê model của provider (kết quả cache 10 phút, không lưu key); với ChatGPT, worker OpenCode của người dùng trả về các model OpenAI mà phiên đăng nhập được dùng. Khi provider không trả danh sách, có thể gõ ID model và chọn mục **Dùng ID tự nhập**.
8. Mỗi nhóm trong combobox ghi rõ nguồn key đang dùng (cá nhân, dùng chung hoặc tài khoản ChatGPT); request gửi đúng nguồn đó. Sai key/rate limit không tự chuyển nguồn để tránh thay đổi tài khoản thanh toán ngoài ý muốn. `AI_ALLOW_SHARED_KEYS=false` chặn dùng key chung ở cấp server.
9. Mọi câu trả lời chạy qua OpenCode; không còn lựa chọn engine. Tra cứu luôn là ngữ nghĩa + số hiệu/điều. Khi embedding không dùng được (ví dụ embedding OpenAI mà không có key OpenAI phù hợp), hệ thống tự tra theo số hiệu/điều và ghi chú `embedding_unavailable` trong câu trả lời; không mượn key OpenAI chung khi đã chọn key cá nhân.

Key env `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` vẫn hoạt động như key chung legacy nếu chưa có bản ghi shared. Bản ghi shared đã tắt/gỡ sẽ chặn fallback về env, tránh vô tình dùng lại key cũ. Key ở env được quản lý qua cấu hình server; UI chỉ gỡ bản ghi đã lưu. API usage theo billing/hạn mức tài khoản sở hữu key, không tương đương plan usage OAuth.

Không gọi API trả phí chỉ để lưu key. Adapter dùng timeout, không tự retry model call. Claude không tự chọn model theo phiên bản mới nhất; nhập ID được cấp để tránh giả định quyền truy cập/chi phí. Câu trả lời chưa kết thúc hoặc bị cắt không được coi là thành công.

## API

Yêu cầu cần phiên cookie hợp lệ hoặc Firebase ID token và profile active. Path provider nhận `openai`, `anthropic`, `deepseek` hoặc `openrouter`.

| Endpoint | Quyền | Payload/hành vi |
|---|---|---|
| GET `/api/v1/ai/connections` | User | Metadata key cá nhân hiện tại + key chung; trạng thái kho mã hóa và phương thức OAuth |
| GET `/api/v1/ai/models` | User | `{groups: [{id, provider, source, label, models: [{id, name}], error}], apiKeysAvailable}` cho các kết nối dùng được; lỗi từng provider nằm trong `error`, không làm hỏng cả danh sách |
| PUT `/api/v1/ai/connections/{provider}` | User | `{apiKey, expectedVersion, enabled}`; chỉ key của chính UID |
| DELETE `/api/v1/ai/connections/{provider}` | User | If-Match bằng version hiện tại |
| PUT `/api/v1/admin/ai/connections/{provider}` | Admin | Payload tương tự; key chung cho hệ thống |
| DELETE `/api/v1/admin/ai/connections/{provider}` | Admin | If-Match; xóa credential và giữ tombstone/audit |

expectedVersion=0 cho lần tạo đầu; dùng version được trả về khi thay/gỡ key. Version sai trả 409. Body từ chối ownerId và trường dư. Lỗi validation không echo key. API không trả credential, ciphertext hay fingerprint của key.

Ví dụ request RAG (giao diện điền `provider`, `credential_source` và `model` theo mục đã chọn trong combobox):

```json
{
  "question": "Hợp đồng cần có nội dung gì?",
  "top_k": 5,
  "provider": "anthropic",
  "credential_source": "personal",
  "model": "MODEL_ID_FROM_YOUR_CONSOLE"
}
```

`engine` chỉ nhận `opencode` (mặc định); `credential_source=chatgpt` chỉ đi với `provider=openai`. `retrieval_mode` mặc định `hybrid`; `keyword` vẫn được API chấp nhận nhưng giao diện không còn hiển thị lựa chọn này. Response bổ sung provider và credential_source thực tế để giao diện hiển thị nguồn đã dùng. Cả hai chế độ vẫn chỉ lấy tối đa 100 chunk theo thiết kế RAG hiện có.

## Lưu trữ và kiểm thử

Collection `ai_connections` dùng ID hash từ owner/provider. Owner là `user:{uid}` hoặc `system`. Chỉ backend truy cập; deny-all client rules hiện có áp dụng. Bản ghi gồm ownerId, provider, authType, encryptedCredential, enabled, version và timestamps. Ciphertext chứa owner/provider bên trong dữ liệu có xác thực; chuyển ciphertext sang tài khoản khác sẽ không dùng được. Update/delete có kiểm tra version và audit commit cùng transaction. Audit chỉ có metadata sự kiện, không có secret.

UI hỏi đáp gọi API thực tế theo lựa chọn; khi chưa đăng nhập vẫn lưu câu hỏi demo trên thiết bị. Khi đã đăng nhập, câu hỏi/câu trả lời ở bộ nhớ trong phiên, được dọn khi đổi tài khoản/đăng xuất. Đây chưa phải lịch sử hội thoại server. Thư viện tài liệu demo vẫn là local theo phạm vi frontend trước đó.

Test dùng key giả và provider HTTP mock: mã hóa, cách ly account, admin guard, version, nguồn key, lỗi provider không rò secret, không fallback billing, và Claude keyword không phụ thuộc key embedding. Chưa xác minh live key/quota, quyền ChatGPT hosted hoặc thực hiện inference trả phí.


## Kết quả xác minh 2026-11-02

- 51 test đạt: 43 unit/API/provider-contract + 8 integration qua Firebase Emulator Auth/Firestore/Storage, gồm lưu/gỡ key mã hóa với quyền Firebase thật.
- Kiểm tra OpenAI SDK 1.109.1 đúng khoảng phiên bản trong requirements, HTTP tới provider được mock.
- Ruff lint/format, compileall, frontend typecheck và production build đều đạt.
- Chromium smoke test đạt login/bootstrap, key cá nhân + key chung của admin, gửi câu hỏi theo provider/source/model/retrieval đã chọn, cách ly secret khỏi localStorage, dọn phiên khi logout và layout desktop/mobile.
- Không dùng credential thật hoặc gửi inference tính phí. Chưa cấu hình deploy cloud/quyền hosted OAuth.

## OpenCode worker

`POST /api/v1/rag/ask` luôn chạy qua OpenCode. Worker dùng API key OpenAI, Claude (Anthropic), DeepSeek và OpenRouter của cá nhân hoặc hệ thống, hoặc ChatGPT OAuth cá nhân theo hướng dẫn bên dưới. Mặc định worker API key chỉ phục vụ client local (`OPENCODE_LOCAL_ENABLED`, chỉ cho `APP_ENV=development`). Bản hosted bật `OPENCODE_API_KEYS_HOSTED_ENABLED=true` và `OPENCODE_CHATGPT_HOSTED_ENABLED=true` (xem `scripts/start-cloud-demo.sh`); khi đó máy chạy API phải có Docker, vì mỗi request vẫn dùng container cô lập như local. Không đặt Docker socket vào container FastAPI.

Để chạy local trên host có Docker:

1. Cài [OpenCode](https://opencode.ai/docs/) phiên bản `1.17.11` và cài các dependency backend. Tạo Python image local: `docker build -f infra/docker/Dockerfile.api -t legal-api-backend:verify apps/api`.
2. Đặt `APP_ENV=development`, `OPENCODE_LOCAL_ENABLED=true`, `OPENCODE_BINARY=/đường/dẫn/đến/opencode` và `OPENCODE_IMAGE=legal-api-backend:verify` trong `apps/api/.env`. Thiết lập `AI_CREDENTIAL_ENCRYPTION_KEY` ổn định trước khi lưu API key; không thay khóa khi còn credential đã mã hóa.
3. Chạy API **trực tiếp trên host**, bind `127.0.0.1` với `--no-proxy-headers`; không chạy runner này trong container API và không đưa API ra mạng công cộng. Backend host cần quyền dùng Docker; Docker daemon là quyền quản trị máy, chỉ dùng môi trường phát triển tin cậy.
4. Đăng nhập ứng dụng, lưu API key của provider tại **Kết nối AI**, rồi chọn model trong ô **Model AI** ở trang Hỏi đáp. API key có billing riêng, không tính vào ChatGPT Plus.

Mỗi câu hỏi OpenCode tạo Docker network nội bộ, gateway và worker riêng; worker non-root, tắt tools/plugins, dùng filesystem tạm, không mount workspace hay credential Firebase. Gateway chỉ chuyển request HTTPS tới endpoint cố định của provider đã chọn (Anthropic xác thực bằng header `x-api-key`; các provider khác dùng `Authorization: Bearer`), kiểm tra TLS và địa chỉ IP công cộng, tối đa ba request và giới hạn output; key được truyền tới worker qua stdin. Có giới hạn thời gian và dọn container/network sau request. Đây là cấu hình local thử nghiệm: chưa kiểm thử đầy đủ OAuth, daemon crash recovery, tải nhiều replica, cơ chế cô lập production hoặc inference thành công bằng API key thật; không dùng làm worker production.

### Thử ChatGPT OAuth local

Đặt `OPENCODE_CHATGPT_LOCAL_ENABLED=true` và `OPENCODE_LOCAL_ENABLED=true` trên máy phát triển, rồi khởi động lại backend. Tại **Kết nối AI**, chọn **Kết nối ChatGPT Plus/Pro**, mở trang OpenAI theo hướng dẫn, sau đó bấm **Tôi đã đăng nhập**. Nhóm **ChatGPT Plus/Pro** xuất hiện trong ô Model AI với các model mà phiên đăng nhập được dùng và được chọn sẵn. Không chia sẻ mã đăng nhập hay token.

Mỗi người dùng có một container OpenCode riêng, credential ở filesystem tạm trong container, không ghi vào Firestore và không dùng key dự phòng. Mạng của worker đi qua tunnel cho phép các domain OpenAI cố định. Đây là phiên thử nghiệm một tiến trình: backend khởi động lại hoặc phiên hết hạn sau tối đa một giờ sẽ phải kết nối lại. Giới hạn tối đa hai phiên; chưa phải giải pháp production, chưa có lưu và làm mới credential bền vững, đồng bộ nhiều replica, khôi phục sau sự cố, hoặc giới hạn số token ở gateway cho OAuth.

OpenCode Free chưa được bật: các lần kiểm tra thực tế tại môi trường này chưa nhận được phản hồi và [tài liệu OpenCode](https://opencode.ai/v2/docs/console/api/inference/) giới hạn free tier cho OpenCode. Chưa xác minh được quyền và tính ổn định khi vận hành worker cho website dùng chung. Không tự chuyển sang model có phí. [OpenAI Docs](https://developers.openai.com/siwc/token-sharing-open-source) hướng dẫn đăng ký quan tâm đối với ứng dụng hosted từ xa; phiên OAuth này chỉ dành cho thử nghiệm local.
