# Kế hoạch triển khai Legal AI Assistant: Firebase Hosting + Cloudflare Tunnel + Local Nemotron

Mình đã kiểm tra phiên bản mới nhất của repository [teddywristh/G1_Web_Design](https://github.com/teddywristh/G1_Web_Design?utm_source=chatgpt.com), bao gồm commit `c69a4b7` ngày 03/11/2026:

[feat: host Nemotron embeddings locally and integrate Firebase demo](https://github.com/teddywristh/G1_Web_Design/commit/c69a4b759aa060a147baf91997e98e2702f1d6ca?utm_source=chatgpt.com)

Kết luận: Kiến trúc hiện tại đã đủ nền tảng để triển khai demo mà không cần Google Cloud Run. Phần lớn công việc còn lại nằm ở networking, authentication, cấu hình Firebase Cloud và kiểm soát bảo mật khi public backend.

Có một quyết định kiến trúc quan trọng:

Chỉ public FastAPI backend qua Cloudflare Tunnel. Không public trực tiếp Nemotron Embedding Service ở port 8010.

## 1. Kiến trúc đích

\#chatgpt-mermaid-\_r_4om\_{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;fill:rgb(13, 13, 13);}@keyframes edge-animation-frame{from{stroke-dashoffset:0;}}@keyframes dash{to{stroke-dashoffset:0;}}#chatgpt-mermaid-\_r_4om\_ .edge-animation-slow{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 50s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_4om\_ .edge-animation-fast{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 20s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_4om\_ .error-icon{fill:rgb(243, 243, 243);}#chatgpt-mermaid-\_r_4om\_ .error-text{fill:rgb(13, 13, 13);stroke:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_4om\_ .edge-thickness-normal{stroke-width:1px;}#chatgpt-mermaid-\_r_4om\_ .edge-thickness-thick{stroke-width:3.5px;}#chatgpt-mermaid-\_r_4om\_ .edge-pattern-solid{stroke-dasharray:0;}#chatgpt-mermaid-\_r_4om\_ .edge-thickness-invisible{stroke-width:0;fill:none;}#chatgpt-mermaid-\_r_4om\_ .edge-pattern-dashed{stroke-dasharray:3;}#chatgpt-mermaid-\_r_4om\_ .edge-pattern-dotted{stroke-dasharray:2;}#chatgpt-mermaid-\_r_4om\_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_4om\_ .marker.cross{stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_4om\_ svg{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;}#chatgpt-mermaid-\_r_4om\_ p{margin:0;}#chatgpt-mermaid-\_r_4om\_ .label{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_4om\_ .cluster-label text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_4om\_ .cluster-label span{color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_4om\_ .cluster-label span p{background-color:transparent;}#chatgpt-mermaid-\_r_4om\_ .label text,#chatgpt-mermaid-\_r_4om\_ span{fill:rgb(13, 13, 13);color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_4om\_ .node rect,#chatgpt-mermaid-\_r_4om\_ .node circle,#chatgpt-mermaid-\_r_4om\_ .node ellipse,#chatgpt-mermaid-\_r_4om\_ .node polygon,#chatgpt-mermaid-\_r_4om\_ .node path{fill:rgb(222, 234, 251);stroke:rgb(83, 154, 248);stroke-width:1px;}#chatgpt-mermaid-\_r_4om\_ .rough-node .label text,#chatgpt-mermaid-\_r_4om\_ .node .label text,#chatgpt-mermaid-\_r_4om\_ .image-shape .label,#chatgpt-mermaid-\_r_4om\_ .icon-shape .label{text-anchor:middle;}#chatgpt-mermaid-\_r_4om\_ .node .katex path{fill:#000;stroke:#000;stroke-width:1px;}#chatgpt-mermaid-\_r_4om\_ .rough-node .label,#chatgpt-mermaid-\_r_4om\_ .node .label,#chatgpt-mermaid-\_r_4om\_ .image-shape .label,#chatgpt-mermaid-\_r_4om\_ .icon-shape .label{text-align:center;}#chatgpt-mermaid-\_r_4om\_ .node.clickable{cursor:pointer;}#chatgpt-mermaid-\_r_4om\_ .root .anchor path{fill:rgb(143, 143, 143)!important;stroke-width:0;stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_4om\_ .arrowheadPath{fill:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_4om\_ .edgePath .path{stroke:rgb(143, 143, 143);stroke-width:1px;}#chatgpt-mermaid-\_r_4om\_ .flowchart-link{stroke:rgb(143, 143, 143);fill:none;}#chatgpt-mermaid-\_r_4om\_ .edgeLabel{background-color:rgb(252, 252, 252);text-align:center;}#chatgpt-mermaid-\_r_4om\_ .edgeLabel p{background-color:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_4om\_ .edgeLabel rect{opacity:0.5;background-color:rgb(252, 252, 252);fill:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_4om\_ .labelBkg{background-color:rgba(252, 252, 252, 0.5);}#chatgpt-mermaid-\_r_4om\_ .cluster rect{fill:rgb(243, 243, 243);stroke:rgba(0, 0, 0, 0.1);stroke-width:1px;}#chatgpt-mermaid-\_r_4om\_ .cluster text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_4om\_ .cluster span{color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_4om\_ div.mermaidTooltip{position:absolute;text-align:center;max-width:200px;padding:2px;font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:12px;background:rgb(243, 243, 243);border:1px solid rgba(0, 0, 0, 0.1);border-radius:2px;pointer-events:none;z-index:100;}#chatgpt-mermaid-\_r_4om\_ .flowchartTitleText{text-anchor:middle;font-size:18px;fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_4om\_ rect.text{fill:none;stroke-width:0;}#chatgpt-mermaid-\_r_4om\_ .icon-shape,#chatgpt-mermaid-\_r_4om\_ .image-shape{background-color:rgb(252, 252, 252);text-align:center;}#chatgpt-mermaid-\_r_4om\_ .icon-shape p,#chatgpt-mermaid-\_r_4om\_ .image-shape p{background-color:rgb(252, 252, 252);padding:2px;}#chatgpt-mermaid-\_r_4om\_ .icon-shape .label rect,#chatgpt-mermaid-\_r_4om\_ .image-shape .label rect{opacity:0.5;background-color:rgb(252, 252, 252);fill:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_4om\_ .label-icon{display:inline-block;height:1em;overflow:visible;vertical-align:-0.125em;}#chatgpt-mermaid-\_r_4om\_ .node .label-icon path{fill:currentColor;stroke:revert;stroke-width:revert;}#chatgpt-mermaid-\_r_4om\_ .node .neo-node{stroke:rgb(83, 154, 248);}#chatgpt-mermaid-\_r_4om\_ [data-look="neo"].node rect,#chatgpt-mermaid-\_r_4om\_ [data-look="neo"].cluster rect,#chatgpt-mermaid-\_r_4om\_ [data-look="neo"].node polygon{stroke:url(#chatgpt-mermaid-\_r_4om\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_4om\_ [data-look="neo"].swimlane.cluster rect{filter:none;}#chatgpt-mermaid-\_r_4om\_ [data-look="neo"].node path{stroke:url(#chatgpt-mermaid-\_r_4om\_-gradient);stroke-width:1px;}#chatgpt-mermaid-\_r_4om\_ [data-look="neo"].node .outer-path{filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_4om\_ [data-look="neo"].node .neo-line path{stroke:rgb(83, 154, 248);filter:none;}#chatgpt-mermaid-\_r_4om\_ [data-look="neo"].node circle{stroke:url(#chatgpt-mermaid-\_r_4om\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_4om\_ [data-look="neo"].node circle .state-start{fill:#000000;}#chatgpt-mermaid-\_r_4om\_ [data-look="neo"].icon-shape .icon{fill:url(#chatgpt-mermaid-\_r_4om\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_4om\_ [data-look="neo"].icon-shape .icon-neo path{stroke:url(#chatgpt-mermaid-\_r_4om\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_4om\_ .node text{font-size:14px;font-weight:600;letter-spacing:normal;fill:rgb(65, 65, 65);}#chatgpt-mermaid-\_r_4om\_ .edgeLabels text{font-size:13px;font-weight:600;letter-spacing:-0.08px;fill:rgb(65, 65, 65);}#chatgpt-mermaid-\_r_4om\_ .node tspan[font-weight="normal"],#chatgpt-mermaid-\_r_4om\_ .edgeLabels tspan[font-weight="normal"]{font-weight:600;}#chatgpt-mermaid-\_r_4om\_ .edgeLabel .label rect{opacity:1;rx:13px;ry:13px;fill:rgb(252, 252, 252);stroke:rgb(219, 219, 219);stroke-width:1px;}#chatgpt-mermaid-\_r_4om\_ .node rect,#chatgpt-mermaid-\_r_4om\_ .node circle,#chatgpt-mermaid-\_r_4om\_ .node ellipse,#chatgpt-mermaid-\_r_4om\_ .node polygon,#chatgpt-mermaid-\_r_4om\_ .node path{fill:rgb(243, 243, 243);stroke:rgba(0, 0, 0, 0.1);stroke-width:1px;}#chatgpt-mermaid-\_r_4om\_ .node rect{rx:16px;ry:16px;}#chatgpt-mermaid-\_r_4om\_ .mermaid-decision .label-container{fill:rgb(249, 249, 249);stroke:rgb(219, 219, 219);stroke-dasharray:2,2;}#chatgpt-mermaid-\_r_4om\_ .edgePaths .flowchart-link{stroke:rgb(143, 143, 143);stroke-width:1px;stroke-linecap:round;stroke-linejoin:round;}#chatgpt-mermaid-\_r_4om\_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_4om\_ :root{--mermaid-font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";}Trình duyệt của thầyFirebase HostingHTML / CSS / JavaScriptCloudflare TunnelHTTPS API endpointFastAPI Backendlocalhost:8000Nemotron 3.5 Embed 1BGPU RTX 3050 · localhost:8010PDF Ingestion WorkerFirebase CloudAuth · Firestore · StorageLLM ProviderAnswer generationHTTPS API requestsQuery embeddingsData, sessions, vectorsAnswer generationPassage embeddingsPDFs, processing jobs, indexes

Đây là kiến trúc hybrid: frontend và dữ liệu được đặt trên cloud, còn AI execution được giữ trên máy cá nhân.

| Thành phần         | Nơi chạy                      | Endpoint                     | Public?                              |
| ------------------ | ----------------------------- | ---------------------------- | ------------------------------------ |
| Frontend           | Firebase Hosting              | `https://PROJECT_ID.web.app` | Có                                   |
| Cloudflare Tunnel  | Máy cá nhân + Cloudflare Edge | HTTPS hostname               | Có                                   |
| FastAPI            | Máy cá nhân                   | `127.0.0.1:8000`             | Chỉ qua Tunnel                       |
| Nemotron Embedding | GPU RTX 3050 6GB              | `127.0.0.1:8010`             | Không                                |
| Ingestion Worker   | Máy cá nhân                   | Không cần HTTP port          | Không                                |
| Authentication     | Firebase Cloud + FastAPI      | Backend-managed session      | Qua API                              |
| Firestore          | Firebase Cloud                | Firebase Admin SDK           | Không truy cập trực tiếp từ frontend |
| PDF Storage        | Firebase Cloud Storage        | Firebase Admin SDK           | Backend quản lý                      |
| Answering LLM      | Nhà cung cấp LLM được chọn    | Provider API                 | Backend gọi                          |

Mọi request từ trình duyệt sẽ đi qua FastAPI. Nemotron chỉ phục vụ FastAPI và ingestion worker.

Như vậy, bạn chỉ cần duy trì một public API endpoint, dù hệ thống có nhiều microservice chạy nội bộ.

## 2. Đánh giá code hiện tại

Readiness trước triển khai

Chưa sẵn sàng public

Đánh giá dựa trên source code của commit c69a4b7, không phải kết quả kiểm thử triển khai thực tế.

| Local embedding microservice   | Đã implement  |
| ------------------------------ | ------------- |
| FastAPI → Nemotron             | Đã implement  |
| Ingestion worker → Nemotron    | Đã implement  |
| Embedding profile / reindex    | Đã implement  |
| Firebase Hosting configuration | Chưa có       |
| Cloudflare Tunnel              | Chưa cấu hình |
| Cross-site authentication      | Cần xử lý     |
| Firebase Cloud migration       | Cần xác minh  |
| Public API security            | Cần hardening |

### 2.1. Phần Nemotron vừa được cập nhật

Các thành phần quan trọng:

| File                                                                                                                                                       | Vai trò                                                       |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| [`apps/embedding/app/main.py`](https://github.com/teddywristh/G1_Web_Design/blob/main/apps/embedding/app/main.py?utm_source=chatgpt.com)                   | FastAPI microservice, load model GPU, nhận embedding requests |
| [`apps/api/app/services/embeddings.py`](https://github.com/teddywristh/G1_Web_Design/blob/main/apps/api/app/services/embeddings.py?utm_source=chatgpt.com) | `LocalEmbedding` adapter gọi port 8010                        |
| [`apps/api/app/workers/ingestion.py`](https://github.com/teddywristh/G1_Web_Design/blob/main/apps/api/app/workers/ingestion.py?utm_source=chatgpt.com)     | Tạo passage embeddings trong quá trình ingest PDF             |
| [`apps/api/app/api/v1/rag.py`](https://github.com/teddywristh/G1_Web_Design/blob/main/apps/api/app/api/v1/rag.py?utm_source=chatgpt.com)                   | Tạo query embeddings để hybrid retrieval                      |
| [`apps/api/app/search/base.py`](https://github.com/teddywristh/G1_Web_Design/blob/main/apps/api/app/search/base.py?utm_source=chatgpt.com)                 | Embedding profile, kiểm soát tính tương thích vector          |
| [`scripts/embedding-host.sh`](https://github.com/teddywristh/G1_Web_Design/blob/main/scripts/embedding-host.sh?utm_source=chatgpt.com)                     | Script khởi động microservice                                 |

Điểm tích cực là repo đã có:

- Model `nvidia/Nemotron-3.5-Embed-1B-BF16`.
- Runtime BF16 + SDPA.
- Một Uvicorn worker và khóa giới hạn một inference đồng thời.
- Phân biệt `encode_query()` và `encode_document()`.
- Truncate vector xuống 1536 chiều, sau đó L2 normalize.
- Endpoint `/health`, `/ready`, `/v1/embeddings`.
- Adapter kiểm tra kích thước vector, finite values và normalization.
- Cơ chế đánh dấu tài liệu cần reindex khi embedding profile thay đổi.

Đặc biệt, tài liệu trong repo đã ghi nhận smoke test trên RTX 3050 6GB:

| Chỉ số                   | Kết quả được ghi nhận     |
| ------------------------ | ------------------------- |
| CUDA                     | PyTorch 2.8.0 + CUDA 12.6 |
| Model load               | Thành công                |
| Embedding dimensions     | 1536                      |
| Initial query có warm-up | 65.147 giây               |
| Query sau warm-up        | 0.278 giây                |
| Passage sau warm-up      | 0.041 giây                |

Đây mới là các phép đo smoke test ngắn, chưa phải benchmark tải thực tế.

Điều này giúp giảm đáng kể rủi ro GPU compatibility, vì model đã được thử thành công trên đúng dòng GPU của bạn.

### 2.2. Những vấn đề mới phát hiện

Có năm vấn đề đáng ưu tiên xử lý:

1. `firebase.json` hiện chỉ có Firestore, Storage và Emulator, chưa khai báo Firebase Hosting.
2. `apps/web/index.html` vẫn trỏ API tới `http://127.0.0.1:8000`.
3. `.env.example` vẫn mặc định kết nối Firebase Emulator, không phải Firebase Cloud.
4. Authentication hiện sử dụng session cookie, có thể gặp lỗi third-party cookies khi frontend ở `web.app` và backend ở `trycloudflare.com`.
5. OpenCode/ChatGPT OAuth được thiết kế riêng cho môi trường local. Không nên tự động public các chức năng này qua Tunnel.

Ngoài ra, Docker Compose hiện tại dành cho emulator development. Nó ghi đè các biến Firebase endpoint và chưa nối GPU host qua mạng container. Vì thế, với demo đầu tiên, mình khuyên chạy các Python process trực tiếp trên host, sau đó mới containerize nếu cần.

## 3. Quyết định quan trọng nhất: dùng domain nào?

Mình đề xuất triển khai theo hai giai đoạn.

Giai đoạn A — Quick Tunnel

Thử nghiệm

Frontend: `PROJECT_ID.web.app`

Backend: `random.trycloudflare.com`

Dùng để xác minh HTTPS, CORS và connectivity. Không cần mua domain, nhưng URL thay đổi khi tạo tunnel mới và session cookie có thể bị chặn.

Giai đoạn B — Named Tunnel + Custom Domain

Khuyến nghị cho buổi demo

Frontend: `app.example.com` → Firebase Hosting

Backend: `api.example.com` → Cloudflare Tunnel

Hostname ổn định, sử dụng cùng một site cho authentication, không phải đổi API URL mỗi lần khởi động.

`example.com` ở đây là domain minh họa, cần thay bằng domain mà bạn sở hữu.

Vì sao mình ưu tiên giai đoạn B?

Trong repo, frontend gọi API bằng:

```
credentials: "include"
```

Còn backend sử dụng cookie `legal_session`.

Khi frontend là `PROJECT_ID.web.app`, backend là `api.example.com`, chúng vẫn thuộc hai site khác nhau. `SameSite=None; Secure` cho phép cookie cross-site, nhưng trình duyệt vẫn có thể chặn third-party cookies.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://developer.mozilla.org\&sz=32)

MDN+1



Nếu frontend là `app.example.com` và backend là `api.example.com`, hai origin khác nhau nhưng cùng site:

- Có thể giữ `SameSite=Lax`.
- Vẫn cấu hình CORS rõ ràng.
- Không phụ thuộc vào việc bật third-party cookies.
- Không phải viết lại hệ thống session authentication.

Firebase Hosting hỗ trợ custom domain và tự cấp HTTPS certificate. Named Cloudflare Tunnel hỗ trợ public hostname cố định.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://firebase.google.com\&sz=32)

firebase.google.com+1



Nếu bạn bắt buộc giữ đúng địa chỉ `*.web.app`: vẫn có thể dùng Quick Tunnel để demo thử, nhưng để tương thích đáng tin cậy với mọi trình duyệt, nên phát triển thêm authentication bằng bearer token hoặc một giải pháp same-origin proxy. Đây là thay đổi lớn hơn việc cấu hình Tunnel.

# 4. Implementation plan theo từng phase

## Phase 0 — Chuẩn hóa môi trường demo

P0 · Bắt buộc

Trước tiên, phân biệt ba môi trường:

| Environment          | Frontend         | Backend          | Database           |
| -------------------- | ---------------- | ---------------- | ------------------ |
| Local development    | `127.0.0.1:8085` | `127.0.0.1:8000` | Firebase Emulators |
| Public demo          | Firebase Hosting | Local + Tunnel   | Firebase Cloud     |
| Production tương lai | Firebase Hosting | Cloud Run/VPS    | Firebase Cloud     |

Không sử dụng Firebase Emulators làm database cho website public.

### Task 0.1 — Tách environment configuration

Đề xuất:

```
apps/api/
├── .env.example
├── .env.local.example
└── .env.demo.example

apps/embedding/
└── .env.example
```

Các file `.example` không có secret. Những file `.env` thực chứa credential phải nằm trong `.gitignore`.

Một cấu hình backend demo dự kiến:

```
APP_ENV=production

# Firebase Cloud
FIREBASE_PROJECT_ID=your-real-firebase-project
FIREBASE_STORAGE_BUCKET=your-actual-bucket
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json

# Không cấu hình ba FIREBASE_*_EMULATOR_HOST
# hoặc FIRESTORE_EMULATOR_HOST

# Embedding
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_URL=http://127.0.0.1:8010
LOCAL_EMBEDDING_MODEL=nvidia/Nemotron-3.5-Embed-1B-BF16
LOCAL_EMBEDDING_TIMEOUT_SECONDS=120
LOCAL_EMBEDDING_PROFILE_VERSION=bf16-sdpa-512-l2-v1

EMBEDDING_DIMENSIONS=1536
EMBEDDING_BATCH_SIZE=1
EMBEDDING_MAX_CHUNKS=0

# Browser authentication - nếu cùng site qua custom domain
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax

BACKEND_CORS_ORIGINS=["https://app.example.com"]

# Tắt local-only OpenCode/OAuth khi public
OPENCODE_LOCAL_ENABLED=false
OPENCODE_CHATGPT_LOCAL_ENABLED=false
```

Đối với Quick Tunnel và `web.app`, nếu thử cơ chế cookie cross-site, hai biến tương ứng là:

```
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=none
```

Đây chỉ là điều kiện để cookie có thể hoạt động cross-site, không bảo đảm trình duyệt sẽ chấp nhận nó.

Lưu ý: code `Settings.validate_environment()` hiện đã hỗ trợ `APP_ENV=production` và từ chối emulator trong production. Chúng ta nên tận dụng validation này.

### Task 0.2 — Giữ GPU service độc lập

Cấu hình Nemotron không cần đổi nhiều:

```
EMBEDDING_MODEL_PATH=models/nemotron-3.5-embed-1b
EMBEDDING_DEVICE=cuda
EMBEDDING_DTYPE=bfloat16
EMBEDDING_MAX_LENGTH=512
EMBEDDING_HOST=127.0.0.1
EMBEDDING_PORT=8010
```

Không đổi `EMBEDDING_HOST` thành `0.0.0.0`, vì cả FastAPI và worker đều nằm cùng máy.

### Acceptance criteria

- Backend sử dụng đúng Firebase Cloud project.
- Không có emulator host được cấu hình.
- Port 8010 chỉ listen trên loopback.
- Production config validation thành công.
- Không có secret nào được commit.

## Phase 1 — Chuẩn bị Firebase Cloud

P0 · Bắt buộc

Đây là bước mà nhiều người thường bỏ sót khi chuyển từ local sang public demo.

### Task 1.1 — Xác minh Firebase project

Trong Firebase Console, kiểm tra:

- Firebase Hosting đã được bật.
- Firebase Authentication được bật.
- Firestore Database đã được tạo.
- Cloud Storage bucket tồn tại.
- Backend có service account phù hợp.
- Project ID và bucket name được xác định chính xác.

Một lưu ý về chi phí: từ ngày 03/02/2026, Cloud Storage for Firebase yêu cầu project dùng gói Blaze, kể cả bucket mặc định. Blaze vẫn có một mức sử dụng miễn phí, nhưng cần liên kết billing account.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://firebase.google.com\&sz=32)

firebase.google.com



Đối với bucket mới, tên thường là:

```
PROJECT_ID.firebasestorage.app
```

Không mặc định dùng tên `PROJECT_ID.appspot.com` như trong `.env.example` hiện tại.

### Task 1.2 — Firebase Admin credentials

Vì FastAPI chạy trên máy cá nhân, backend cần Google Application Default Credentials hoặc service account được cấp quyền.

Phạm vi cần kiểm tra:

- Firebase Authentication user operations.
- Firestore read/write/transactions.
- Cloud Storage object read/write/delete/list.

Không đưa file JSON service account vào Firebase Hosting, frontend, Git hoặc Docker image.

### Task 1.3 — Deploy Firestore indexes

Repo đã có vector index 1536 chiều trong:

[`infra/firebase/firestore.indexes.json`](https://github.com/teddywristh/G1_Web_Design/blob/main/infra/firebase/firestore.indexes.json?utm_source=chatgpt.com)

Lệnh triển khai:

```
firebase login

firebase projects:list

firebase deploy \
  --only firestore:indexes \
  --project YOUR_PROJECT_ID
```

Đợi index build xong trước khi chạy semantic retrieval. Đồng thời kiểm tra các index composite cho `processing_jobs`, `auth_sessions`, `knowledge_documents`.

### Task 1.4 — Deploy security rules

Repo hiện dùng deny-all rules cho direct client access, phù hợp với kiến trúc backend-only.

Sau khi review:

```
firebase deploy \
  --only firestore:rules,storage \
  --project YOUR_PROJECT_ID
```

Chỉ chạy với project ID đã xác minh. Không triển khai lên database đang được nhóm khác sử dụng mà chưa kiểm tra tác động của rules.

### Task 1.5 — Chuẩn bị dữ liệu demo

Dữ liệu trong Firebase Emulator sẽ không tự xuất hiện trên Firebase Cloud.

Vì vậy, hãy:

1. Tạo tài khoản demo mới trên Cloud.
2. Tạo knowledge base riêng.
3. Upload PDF thực.
4. Đợi ingestion hoàn thành.
5. Kiểm tra vector retrieval.
6. Giữ sẵn bộ dữ liệu này cho buổi trình bày.

Không cần migrate toàn bộ emulator database nếu dữ liệu chỉ phục vụ development.

## Phase 2 — Khởi động toàn bộ AI backend trên local

P0 · Bắt buộc

Mình đề xuất chạy các service theo đúng thứ tự phụ thuộc.

1. Khởi động Nemotron

   Từ repository root:
   ```
   bash scripts/embedding-host.sh
   ```
   Nếu sử dụng đúng Conda environment đã được ghi trong README:
   ```
   EMBEDDING_PYTHON=/home/minhquang/miniconda3/envs/embed/bin/python \
     bash scripts/embedding-host.sh
   ```
   Kiểm tra:
   ```
   curl -f http://127.0.0.1:8010/ready
   ```
   Phải trả về trạng thái ready, không chỉ process health.
2. Khởi động FastAPI
   ```
   cd apps/api

   python -m uvicorn app.main:app \
     --host 127.0.0.1 \
     --port 8000 \
     --workers 1
   ```
   Kiểm tra:
   ```
   curl -f http://127.0.0.1:8000/health

   curl -f http://127.0.0.1:8000/ready
   ```
3. Khởi động PDF ingestion worker

   Mở terminal khác:
   ```
   cd apps/api

   python -m app.workers.ingestion
   ```
   Worker sử dụng cùng cấu hình Firebase Cloud và embedding provider với backend.
4. Xác minh end-to-end nội bộ

   Kiểm tra lần lượt:
   - Backend kết nối Cloud Firestore.
   - Backend kết nối Firebase Storage.
   - Worker nhận được processing job.
   - Worker gọi Nemotron tại port 8010.
   - Vector được lưu vào Firestore.
   - Query từ FastAPI tạo được query embedding.

Không sử dụng `scripts/local-embed-demo.sh` nguyên trạng cho bước này. Script hiện tại kiểm tra bắt buộc ba Firebase Emulator ports trước khi khởi động các service khác.

Nếu muốn có một lệnh duy nhất để mở demo, nên tạo script mới, ví dụ `scripts/start-cloud-demo.sh`, sử dụng cloud readiness checks thay cho emulator checks.

## Phase 3 — Thiết lập Cloudflare Tunnel

P0 · Bắt buộc

### 3.1. Proof of concept bằng Quick Tunnel

Cài `cloudflared` theo [hướng dẫn chính thức](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/?utm_source=chatgpt.com).

Sau khi FastAPI chạy ở port 8000:

```
cloudflared tunnel --url http://127.0.0.1:8000
```

Cloudflare sẽ trả về một URL dạng:

```
https://random-name.trycloudflare.com
```

Thử:

```
curl -i https://random-name.trycloudflare.com/health
```

Nếu trả `HTTP 200`, request từ Internet đã đi được qua Cloudflare về FastAPI trên máy bạn.

Quick Tunnel được Cloudflare thiết kế cho development/testing; không có cam kết uptime, có giới hạn 200 request đang xử lý đồng thời và không hỗ trợ SSE. Các giới hạn này không phải vấn đề lớn đối với smoke test hiện tại, nhưng URL tạm không nên là endpoint chính thức của demo.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://51e47fea.previews.developers.cloudflare.com\&sz=32)

Cloudflare One docs



### 3.2. Named Tunnel để demo ổn định

Khi đã có domain, tạo Named Tunnel:

1. Mở [Cloudflare Dashboard](https://dash.cloudflare.com/?utm_source=chatgpt.com).
2. Vào Networking → Tunnels.
3. Chọn Create Tunnel.
4. Đặt tên `legal-ai-demo`.
5. Chọn `cloudflared` connector.
6. Cài và chạy connector trên máy có RTX 3050 theo hướng dẫn được cung cấp.
7. Thêm Published Application.

Cấu hình route:

| Field        | Value             |
| ------------ | ----------------- |
| Hostname     | `api.example.com` |
| Service type | `HTTP`            |
| Service URL  | `127.0.0.1:8000`  |
| Connector    | `legal-ai-demo`   |

Cloudflare sẽ định tuyến HTTPS request qua connector tới local FastAPI mà không cần mở inbound port trên router. Named Tunnel cần domain được quản lý trên Cloudflare để publish hostname.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://developers.cloudflare.com\&sz=32)

Cloudflare Docs+1



Nếu dùng CLI thay vì Dashboard, có thể quản lý tunnel bằng cấu hình `ingress` với một catch-all `http_status:404`. Nhưng với demo một service, Dashboard dễ quản lý hơn.

### 3.3. Kiểm tra CORS qua public endpoint

Ví dụ frontend là `https://app.example.com`:

```
curl -i -X OPTIONS \
  https://api.example.com/api/v1/auth/login \
  -H "Origin: https://app.example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,x-csrf-token"
```

Response cần có các header tương ứng:

```
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Credentials: true
```

Không dùng `Access-Control-Allow-Origin: *` cho cookie-based authentication.

### Acceptance criteria

- `/health` qua Tunnel trả 200.
- `/ready` qua Tunnel trả 200.
- OPTIONS preflight hợp lệ.
- API không bị mở trực tiếp qua router port forwarding.
- Port 8010 không có public route.
- API public hoạt động khi dùng mạng khác với máy host.

## Phase 4 — Deploy frontend lên Firebase Hosting

P0 · Bắt buộc

### Task 4.1 — Cập nhật `firebase.json`

File hiện tại chưa có phần `hosting`.

Bổ sung block sau vào JSON hiện có, giữ nguyên cấu hình Firestore, Storage và Emulator:

```
{
  "hosting": {
    "public": "apps/web",
    "ignore": [
      "firebase.json",
      "**/.*",
      "**/node_modules/**",
      "**/src/**",
      "**/*.md",
      "**/*.example"
    ],
    "headers": [
      {
        "source": "**",
        "headers": [
          {
            "key": "X-Content-Type-Options",
            "value": "nosniff"
          }
        ]
      }
    ]
  }
}
```

Trong repo, frontend hiện sử dụng HTML/CSS/JavaScript thuần, nên không cần build React hoặc Next.js.

Đặt `"public": "apps/web"` cho phép Firebase deploy trực tiếp các tài nguyên trong thư mục đó.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://firebase.google.com\&sz=32)

firebase.google.com



### Task 4.2 — Cấu hình frontend API endpoint

File:

[`apps/web/index.html`](https://github.com/teddywristh/G1_Web_Design/blob/main/apps/web/index.html?utm_source=chatgpt.com)

Hiện tại:

```
<meta name="api-base" content="http://127.0.0.1:8000" />
```

Đổi thành:

```
<meta name="api-base" content="https://api.example.com" />
```

`apps/web/api.js` đã tự đọc giá trị này và gửi request đến:

```
const API = `${API_BASE}/api/v1`;
```

Vì vậy, không cần sửa từng API call.

Tuy nhiên, mình đề xuất một cải tiến P1: tách API URL sang file cấu hình môi trường để tránh việc developer đổi URL trong `index.html` mỗi lần chuyển giữa local và demo.

### Task 4.3 — Deploy Firebase Hosting

```
firebase deploy \
  --only hosting \
  --project YOUR_PROJECT_ID
```

Sau khi triển khai, truy cập:

```
https://YOUR_PROJECT_ID.web.app
```

Kiểm tra browser DevTools → Network:

- Frontend JS/CSS trả 200.
- API requests đi đến Tunnel URL.
- Không có request nào đến `127.0.0.1:8000`.
- Không có Mixed Content error.

### Task 4.4 — Gắn custom domain (khuyến nghị)

Trong Firebase Console → Hosting → Add custom domain:

```
app.example.com
```

Với Cloudflare DNS, thêm các bản ghi TXT/A/CNAME theo đúng giá trị Firebase cung cấp. Nên để bản ghi trỏ đến Firebase ở chế độ DNS only trong quá trình xác minh và cấp certificate, rồi kiểm tra trạng thái `Connected`.

Đồng thời duy trì:

```
api.example.com → Cloudflare Tunnel
```

Firebase có thể mất thời gian để xác minh domain và cấp chứng chỉ SSL. Vì vậy, việc này nên hoàn thành trước ngày demo.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://firebase.google.com\&sz=32)

firebase.google.com



## Phase 5 — Authentication, bảo mật và sửa các vấn đề triển khai

P0 · Quan trọng nhất trước khi public

Đây là phase mình muốn nhóm ưu tiên cao.

### 5.1. Session authentication

Hệ thống hiện dùng:

- `legal_session`: HttpOnly session cookie.
- `X-CSRF-Token`: xác thực các request thay đổi dữ liệu.
- Firestore: lưu session và trạng thái thu hồi.

Với custom domain cùng site:

```
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
BACKEND_CORS_ORIGINS=["https://app.example.com"]
```

Giữ frontend:

```
credentials: "include"
```

Sau đó kiểm thử quy trình:

1. Login.
2. Browser lưu `legal_session`.
3. `GET /api/v1/auth/me` trả thông tin người dùng.
4. Request POST có CSRF token hợp lệ.
5. Refresh trang vẫn giữ session.
6. Logout xóa session.

Nếu sử dụng Google Sign-In, cần thêm frontend domain vào Google OAuth Client → Authorized JavaScript origins. Repo đang dùng Google Identity Services, không phải Firebase Auth popup flow.

### 5.2. Không public OpenCode/ChatGPT OAuth local

Mình phát hiện một điểm cần đặc biệt chú ý.

Trong:

- `apps/api/app/api/v1/rag.py`
- `apps/api/app/api/v1/ai_connections.py`

Code kiểm tra local access bằng `request.client.host`.

Nhưng khi request đi qua Cloudflare Tunnel tới FastAPI trên loopback, FastAPI có thể nhìn thấy địa chỉ peer nội bộ của proxy thay vì IP thực của người dùng.

Do đó, không nên dựa vào kiểm tra loopback để bảo vệ chức năng local-only sau khi public qua Tunnel.

Với demo, đề xuất:

```
APP_ENV=production
OPENCODE_LOCAL_ENABLED=false
OPENCODE_CHATGPT_LOCAL_ENABLED=false
```

Đồng thời đảm bảo giao diện không mời người dùng kết nối những chức năng đã bị tắt.

Điều này dẫn đến một yêu cầu quan trọng:

Local embedding miễn phí không đồng nghĩa với toàn bộ RAG không cần API key.

Nemotron chỉ tạo embeddings. Để sinh câu trả lời, hệ thống vẫn cần một answering LLM.

Cho buổi demo, mình đề xuất cấu hình sẵn một LLM provider theo đường gọi API trực tiếp mà backend đã hỗ trợ, ví dụ OpenAI hoặc Anthropic.

Nếu muốn dùng local OpenCode hoặc ChatGPT OAuth từ public website, cần thiết kế lại cơ chế phân quyền và isolation cho riêng chức năng đó.

### 5.3. Giới hạn quyền dùng embedding endpoint

Repo đã thêm:

```
POST /api/v1/embeddings
```

Endpoint này yêu cầu authentication, nhưng mọi người dùng đăng nhập hợp lệ đều có thể gọi embedding inference.

Với RTX 3050 6GB, mình không khuyến nghị cho tất cả người dùng sử dụng endpoint này không giới hạn.

Đề xuất một trong hai phương án:

- Tắt diagnostic embedding endpoint ở public demo, chỉ sử dụng nội bộ từ RAG và ingestion.
- Hoặc giới hạn admin-only, rate limit, input size và concurrency.

Đây là biện pháp bảo vệ GPU, không chỉ là vấn đề chi phí.

### 5.4. Chống đăng ký và sử dụng ngoài dự kiến

Hiện tại API `/auth/register` cho phép tạo tài khoản.

Nếu Tunnel public và bất kỳ ai biết URL đều có thể đăng ký, họ có thể sử dụng tài nguyên Firestore, Storage, embedding và LLM của bạn.

Nên bổ sung chế độ demo:

```
DEMO_REGISTRATION_ENABLED=false
```

Biến này là đề xuất mới, chưa được implement.

Trước khi tắt registration, tạo sẵn tài khoản cho thầy và tài khoản backup.

Có thể bổ sung:

- Allowlist email demo.
- Rate limiting cho login, register, upload, RAG.
- Giới hạn số PDF/người dùng.
- Giới hạn request đồng thời.
- Giới hạn số câu hỏi trong thời gian demo.

CORS không thay thế authentication hay rate limiting, vì các HTTP client ngoài trình duyệt không bị CORS kiểm soát.

### 5.5. Vấn đề Nginx Gateway — có một bug deployment tiềm ẩn

Trong [`infra/nginx/api.conf`](https://github.com/teddywristh/G1_Web_Design/blob/main/infra/nginx/api.conf?utm_source=chatgpt.com), cấu hình mặc định:

```
client_max_body_size 1m;
```

Repo chỉ nâng giới hạn lên `20m` cho đường dẫn upload tài liệu admin.

Nhưng upload knowledge-base PDF mới sử dụng:

```
/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/file
```

Nếu đặt Tunnel trước Nginx hiện tại, PDF lớn hơn 1 MiB có thể bị gateway từ chối với HTTP 413.

Cần thêm rule tương ứng:

```
location ~ ^/api/v1/knowledge-bases/[^/]+/documents/[^/]+/file$ {
    client_max_body_size 20m;
    proxy_request_buffering off;
    proxy_pass http://backend_api;
}
```

Đồng thời cập nhật CORS origin allowlist trong Nginx cho frontend Firebase.

Với phiên bản demo đầu tiên, có thể tunnel trực tiếp đến FastAPI port 8000 để tránh cấu hình Docker emulator hiện tại. Nhưng trước khi public, cần bổ sung rate limiting ở API hoặc một gateway được cấu hình đúng.

## Phase 6 — Tối ưu luồng embedding và RAG cho môi trường public

P1 · Nên hoàn thành

### Vấn đề concurrency

Trong Nemotron microservice hiện tại:

```
self.lock.acquire(blocking=False)
```

Nếu model đang chạy inference, request mới nhận HTTP 429.

`LocalEmbedding` adapter sau đó chuyển lỗi này thành trạng thái embedding busy.

Điều này có thể xuất hiện khi:

- Worker đang embed PDF nhiều trang.
- Thầy đồng thời gửi một câu hỏi.
- Cả hai cùng cần GPU.

Với RTX 3050, mình đề xuất hai lớp điều phối.

| Thành phần       | Chính sách                          |
| ---------------- | ----------------------------------- |
| Embedding host   | Một GPU inference tại một thời điểm |
| RAG query        | Ưu tiên latency, timeout ngắn       |
| Ingestion worker | Background, có thể chờ và retry     |
| GPU queue        | Bounded queue, không nhận vô hạn    |
| Retry            | Backoff có giới hạn                 |
| Monitoring       | Busy rate, latency, GPU memory      |

Hiện tại mình chưa khuyên tăng số workers hoặc load hai bản model lên GPU.

### Cải tiến kiến trúc P1

Thay việc cả query và ingestion cạnh tranh trực tiếp với non-blocking lock, có thể thiết kế một inference scheduler nhỏ:

\#chatgpt-mermaid-\_r_522\_{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;fill:rgb(13, 13, 13);}@keyframes edge-animation-frame{from{stroke-dashoffset:0;}}@keyframes dash{to{stroke-dashoffset:0;}}#chatgpt-mermaid-\_r_522\_ .edge-animation-slow{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 50s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_522\_ .edge-animation-fast{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 20s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_522\_ .error-icon{fill:rgb(243, 243, 243);}#chatgpt-mermaid-\_r_522\_ .error-text{fill:rgb(13, 13, 13);stroke:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_522\_ .edge-thickness-normal{stroke-width:1px;}#chatgpt-mermaid-\_r_522\_ .edge-thickness-thick{stroke-width:3.5px;}#chatgpt-mermaid-\_r_522\_ .edge-pattern-solid{stroke-dasharray:0;}#chatgpt-mermaid-\_r_522\_ .edge-thickness-invisible{stroke-width:0;fill:none;}#chatgpt-mermaid-\_r_522\_ .edge-pattern-dashed{stroke-dasharray:3;}#chatgpt-mermaid-\_r_522\_ .edge-pattern-dotted{stroke-dasharray:2;}#chatgpt-mermaid-\_r_522\_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_522\_ .marker.cross{stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_522\_ svg{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;}#chatgpt-mermaid-\_r_522\_ p{margin:0;}#chatgpt-mermaid-\_r_522\_ .label{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_522\_ .cluster-label text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_522\_ .cluster-label span{color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_522\_ .cluster-label span p{background-color:transparent;}#chatgpt-mermaid-\_r_522\_ .label text,#chatgpt-mermaid-\_r_522\_ span{fill:rgb(13, 13, 13);color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_522\_ .node rect,#chatgpt-mermaid-\_r_522\_ .node circle,#chatgpt-mermaid-\_r_522\_ .node ellipse,#chatgpt-mermaid-\_r_522\_ .node polygon,#chatgpt-mermaid-\_r_522\_ .node path{fill:rgb(222, 234, 251);stroke:rgb(83, 154, 248);stroke-width:1px;}#chatgpt-mermaid-\_r_522\_ .rough-node .label text,#chatgpt-mermaid-\_r_522\_ .node .label text,#chatgpt-mermaid-\_r_522\_ .image-shape .label,#chatgpt-mermaid-\_r_522\_ .icon-shape .label{text-anchor:middle;}#chatgpt-mermaid-\_r_522\_ .node .katex path{fill:#000;stroke:#000;stroke-width:1px;}#chatgpt-mermaid-\_r_522\_ .rough-node .label,#chatgpt-mermaid-\_r_522\_ .node .label,#chatgpt-mermaid-\_r_522\_ .image-shape .label,#chatgpt-mermaid-\_r_522\_ .icon-shape .label{text-align:center;}#chatgpt-mermaid-\_r_522\_ .node.clickable{cursor:pointer;}#chatgpt-mermaid-\_r_522\_ .root .anchor path{fill:rgb(143, 143, 143)!important;stroke-width:0;stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_522\_ .arrowheadPath{fill:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_522\_ .edgePath .path{stroke:rgb(143, 143, 143);stroke-width:1px;}#chatgpt-mermaid-\_r_522\_ .flowchart-link{stroke:rgb(143, 143, 143);fill:none;}#chatgpt-mermaid-\_r_522\_ .edgeLabel{background-color:rgb(252, 252, 252);text-align:center;}#chatgpt-mermaid-\_r_522\_ .edgeLabel p{background-color:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_522\_ .edgeLabel rect{opacity:0.5;background-color:rgb(252, 252, 252);fill:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_522\_ .labelBkg{background-color:rgba(252, 252, 252, 0.5);}#chatgpt-mermaid-\_r_522\_ .cluster rect{fill:rgb(243, 243, 243);stroke:rgba(0, 0, 0, 0.1);stroke-width:1px;}#chatgpt-mermaid-\_r_522\_ .cluster text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_522\_ .cluster span{color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_522\_ div.mermaidTooltip{position:absolute;text-align:center;max-width:200px;padding:2px;font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:12px;background:rgb(243, 243, 243);border:1px solid rgba(0, 0, 0, 0.1);border-radius:2px;pointer-events:none;z-index:100;}#chatgpt-mermaid-\_r_522\_ .flowchartTitleText{text-anchor:middle;font-size:18px;fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_522\_ rect.text{fill:none;stroke-width:0;}#chatgpt-mermaid-\_r_522\_ .icon-shape,#chatgpt-mermaid-\_r_522\_ .image-shape{background-color:rgb(252, 252, 252);text-align:center;}#chatgpt-mermaid-\_r_522\_ .icon-shape p,#chatgpt-mermaid-\_r_522\_ .image-shape p{background-color:rgb(252, 252, 252);padding:2px;}#chatgpt-mermaid-\_r_522\_ .icon-shape .label rect,#chatgpt-mermaid-\_r_522\_ .image-shape .label rect{opacity:0.5;background-color:rgb(252, 252, 252);fill:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_522\_ .label-icon{display:inline-block;height:1em;overflow:visible;vertical-align:-0.125em;}#chatgpt-mermaid-\_r_522\_ .node .label-icon path{fill:currentColor;stroke:revert;stroke-width:revert;}#chatgpt-mermaid-\_r_522\_ .node .neo-node{stroke:rgb(83, 154, 248);}#chatgpt-mermaid-\_r_522\_ [data-look="neo"].node rect,#chatgpt-mermaid-\_r_522\_ [data-look="neo"].cluster rect,#chatgpt-mermaid-\_r_522\_ [data-look="neo"].node polygon{stroke:url(#chatgpt-mermaid-\_r_522\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_522\_ [data-look="neo"].swimlane.cluster rect{filter:none;}#chatgpt-mermaid-\_r_522\_ [data-look="neo"].node path{stroke:url(#chatgpt-mermaid-\_r_522\_-gradient);stroke-width:1px;}#chatgpt-mermaid-\_r_522\_ [data-look="neo"].node .outer-path{filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_522\_ [data-look="neo"].node .neo-line path{stroke:rgb(83, 154, 248);filter:none;}#chatgpt-mermaid-\_r_522\_ [data-look="neo"].node circle{stroke:url(#chatgpt-mermaid-\_r_522\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_522\_ [data-look="neo"].node circle .state-start{fill:#000000;}#chatgpt-mermaid-\_r_522\_ [data-look="neo"].icon-shape .icon{fill:url(#chatgpt-mermaid-\_r_522\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_522\_ [data-look="neo"].icon-shape .icon-neo path{stroke:url(#chatgpt-mermaid-\_r_522\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_522\_ .node text{font-size:14px;font-weight:600;letter-spacing:normal;fill:rgb(65, 65, 65);}#chatgpt-mermaid-\_r_522\_ .edgeLabels text{font-size:13px;font-weight:600;letter-spacing:-0.08px;fill:rgb(65, 65, 65);}#chatgpt-mermaid-\_r_522\_ .node tspan[font-weight="normal"],#chatgpt-mermaid-\_r_522\_ .edgeLabels tspan[font-weight="normal"]{font-weight:600;}#chatgpt-mermaid-\_r_522\_ .edgeLabel .label rect{opacity:1;rx:13px;ry:13px;fill:rgb(252, 252, 252);stroke:rgb(219, 219, 219);stroke-width:1px;}#chatgpt-mermaid-\_r_522\_ .node rect,#chatgpt-mermaid-\_r_522\_ .node circle,#chatgpt-mermaid-\_r_522\_ .node ellipse,#chatgpt-mermaid-\_r_522\_ .node polygon,#chatgpt-mermaid-\_r_522\_ .node path{fill:rgb(243, 243, 243);stroke:rgba(0, 0, 0, 0.1);stroke-width:1px;}#chatgpt-mermaid-\_r_522\_ .node rect{rx:16px;ry:16px;}#chatgpt-mermaid-\_r_522\_ .mermaid-decision .label-container{fill:rgb(249, 249, 249);stroke:rgb(219, 219, 219);stroke-dasharray:2,2;}#chatgpt-mermaid-\_r_522\_ .edgePaths .flowchart-link{stroke:rgb(143, 143, 143);stroke-width:1px;stroke-linecap:round;stroke-linejoin:round;}#chatgpt-mermaid-\_r_522\_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_522\_ :root{--mermaid-font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";}RAG QueryIngestion WorkerEmbedding SchedulerBounded QueueNemotron GPUConcurrency = 1Higher priorityBackground priority

Đây là cải tiến tương lai, chưa cần xây ngay nếu benchmark cho thấy contention thấp.

### Cần benchmark những gì?

| Test               | Điều kiện cần đo                  |
| ------------------ | --------------------------------- |
| Cold startup       | Model loading time                |
| Query warm-up      | Latency lần đầu                   |
| Query latency      | p50 / p95                         |
| PDF 10 trang       | Tổng thời gian ingestion          |
| PDF 50 trang       | Throughput và memory              |
| PDF 300 trang      | Stability, retry, processing time |
| Concurrent request | Query khi worker đang embed       |
| Recovery           | Restart worker giữa chừng         |
| Semantic retrieval | Recall\@5, citation accuracy      |

Với buổi demo, nên chuẩn bị hai nhóm tài liệu:

- PDF ngắn 5–15 trang: thầy upload trực tiếp để quan sát ingestion.
- PDF lớn 100–300 trang: đã được index trước, để test RAG và citation ngay lập tức.

Như vậy, thầy vẫn kiểm tra được cả upload workflow và khả năng truy vấn trên tài liệu dài.

## Phase 7 — End-to-end testing trên một thiết bị khác

P0 · Điều kiện Go/No-Go

Đây là test matrix mình đề xuất.

| ID  | Test case                   | Kết quả mong đợi                     |
| --- | --------------------------- | ------------------------------------ |
| T01 | Truy cập Firebase Hosting   | Giao diện hiển thị đầy đủ            |
| T02 | Gọi public `/health`        | HTTP 200                             |
| T03 | Gọi public `/ready`         | Firebase Cloud dependencies sẵn sàng |
| T04 | Login                       | Session cookie được lưu              |
| T05 | Refresh trang               | Session được khôi phục               |
| T06 | Tạo knowledge base          | Metadata lưu Firestore               |
| T07 | Upload PDF 5–15 trang       | File lưu Storage                     |
| T08 | Worker xử lý tài liệu       | Job tiến tới trạng thái thành công   |
| T09 | Vector indexing             | 1536 chiều, đúng embedding profile   |
| T10 | Hybrid retrieval            | Tìm được đoạn phù hợp                |
| T11 | LLM answer                  | Sinh câu trả lời                     |
| T12 | Citation                    | Mở đúng tài liệu và đoạn trích       |
| T13 | PDF download                | File tải về thành công               |
| T14 | Logout                      | Session bị thu hồi                   |
| T15 | API khi tắt backend         | Trả lỗi rõ ràng, không treo UI       |
| T16 | Restart worker              | Job có thể tiếp tục hoặc retry       |
| T17 | Query khi worker đang embed | Hệ thống xử lý busy có kiểm soát     |
| T18 | Thử trình duyệt khác        | Authentication vẫn hoạt động         |

Thực hiện tối thiểu trên:

- Máy của bạn.
- Máy khác dùng mạng Internet khác.
- Chrome hoặc Edge với third-party cookies bị chặn.

Nếu demo dùng custom domain, nên kiểm thử cả truy cập `app.example.com` và `PROJECT_ID.web.app`, vì hai địa chỉ có thể có hành vi cookie khác nhau.

### Bộ test tự động nên bổ sung

Trong repository:

```
apps/api/tests/
├── test_public_auth_cors.py
├── test_cloud_config.py
├── test_tunnel_request_contract.py
├── test_embedding_contention.py
└── test_demo_smoke.py
```

Không nhất thiết phải kiểm thử Cloudflare thật trong unit test. Dùng integration test cho HTTP contract và một bộ smoke test riêng với public endpoint.

## Phase 8 — Operations runbook cho ngày demo

P1 · Rất nên có

Mục tiêu: trước khi thầy mở website, bạn có thể bật hệ thống và kiểm tra readiness trong vài phút.

### Startup sequence

\#chatgpt-mermaid-\_r_52e\_{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;fill:rgb(13, 13, 13);}@keyframes edge-animation-frame{from{stroke-dashoffset:0;}}@keyframes dash{to{stroke-dashoffset:0;}}#chatgpt-mermaid-\_r_52e\_ .edge-animation-slow{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 50s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_52e\_ .edge-animation-fast{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 20s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_52e\_ .error-icon{fill:rgb(243, 243, 243);}#chatgpt-mermaid-\_r_52e\_ .error-text{fill:rgb(13, 13, 13);stroke:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_52e\_ .edge-thickness-normal{stroke-width:1px;}#chatgpt-mermaid-\_r_52e\_ .edge-thickness-thick{stroke-width:3.5px;}#chatgpt-mermaid-\_r_52e\_ .edge-pattern-solid{stroke-dasharray:0;}#chatgpt-mermaid-\_r_52e\_ .edge-thickness-invisible{stroke-width:0;fill:none;}#chatgpt-mermaid-\_r_52e\_ .edge-pattern-dashed{stroke-dasharray:3;}#chatgpt-mermaid-\_r_52e\_ .edge-pattern-dotted{stroke-dasharray:2;}#chatgpt-mermaid-\_r_52e\_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_52e\_ .marker.cross{stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_52e\_ svg{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;}#chatgpt-mermaid-\_r_52e\_ p{margin:0;}#chatgpt-mermaid-\_r_52e\_ .label{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_52e\_ .cluster-label text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_52e\_ .cluster-label span{color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_52e\_ .cluster-label span p{background-color:transparent;}#chatgpt-mermaid-\_r_52e\_ .label text,#chatgpt-mermaid-\_r_52e\_ span{fill:rgb(13, 13, 13);color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_52e\_ .node rect,#chatgpt-mermaid-\_r_52e\_ .node circle,#chatgpt-mermaid-\_r_52e\_ .node ellipse,#chatgpt-mermaid-\_r_52e\_ .node polygon,#chatgpt-mermaid-\_r_52e\_ .node path{fill:rgb(222, 234, 251);stroke:rgb(83, 154, 248);stroke-width:1px;}#chatgpt-mermaid-\_r_52e\_ .rough-node .label text,#chatgpt-mermaid-\_r_52e\_ .node .label text,#chatgpt-mermaid-\_r_52e\_ .image-shape .label,#chatgpt-mermaid-\_r_52e\_ .icon-shape .label{text-anchor:middle;}#chatgpt-mermaid-\_r_52e\_ .node .katex path{fill:#000;stroke:#000;stroke-width:1px;}#chatgpt-mermaid-\_r_52e\_ .rough-node .label,#chatgpt-mermaid-\_r_52e\_ .node .label,#chatgpt-mermaid-\_r_52e\_ .image-shape .label,#chatgpt-mermaid-\_r_52e\_ .icon-shape .label{text-align:center;}#chatgpt-mermaid-\_r_52e\_ .node.clickable{cursor:pointer;}#chatgpt-mermaid-\_r_52e\_ .root .anchor path{fill:rgb(143, 143, 143)!important;stroke-width:0;stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_52e\_ .arrowheadPath{fill:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_52e\_ .edgePath .path{stroke:rgb(143, 143, 143);stroke-width:1px;}#chatgpt-mermaid-\_r_52e\_ .flowchart-link{stroke:rgb(143, 143, 143);fill:none;}#chatgpt-mermaid-\_r_52e\_ .edgeLabel{background-color:rgb(252, 252, 252);text-align:center;}#chatgpt-mermaid-\_r_52e\_ .edgeLabel p{background-color:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_52e\_ .edgeLabel rect{opacity:0.5;background-color:rgb(252, 252, 252);fill:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_52e\_ .labelBkg{background-color:rgba(252, 252, 252, 0.5);}#chatgpt-mermaid-\_r_52e\_ .cluster rect{fill:rgb(243, 243, 243);stroke:rgba(0, 0, 0, 0.1);stroke-width:1px;}#chatgpt-mermaid-\_r_52e\_ .cluster text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_52e\_ .cluster span{color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_52e\_ div.mermaidTooltip{position:absolute;text-align:center;max-width:200px;padding:2px;font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:12px;background:rgb(243, 243, 243);border:1px solid rgba(0, 0, 0, 0.1);border-radius:2px;pointer-events:none;z-index:100;}#chatgpt-mermaid-\_r_52e\_ .flowchartTitleText{text-anchor:middle;font-size:18px;fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_52e\_ rect.text{fill:none;stroke-width:0;}#chatgpt-mermaid-\_r_52e\_ .icon-shape,#chatgpt-mermaid-\_r_52e\_ .image-shape{background-color:rgb(252, 252, 252);text-align:center;}#chatgpt-mermaid-\_r_52e\_ .icon-shape p,#chatgpt-mermaid-\_r_52e\_ .image-shape p{background-color:rgb(252, 252, 252);padding:2px;}#chatgpt-mermaid-\_r_52e\_ .icon-shape .label rect,#chatgpt-mermaid-\_r_52e\_ .image-shape .label rect{opacity:0.5;background-color:rgb(252, 252, 252);fill:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_52e\_ .label-icon{display:inline-block;height:1em;overflow:visible;vertical-align:-0.125em;}#chatgpt-mermaid-\_r_52e\_ .node .label-icon path{fill:currentColor;stroke:revert;stroke-width:revert;}#chatgpt-mermaid-\_r_52e\_ .node .neo-node{stroke:rgb(83, 154, 248);}#chatgpt-mermaid-\_r_52e\_ [data-look="neo"].node rect,#chatgpt-mermaid-\_r_52e\_ [data-look="neo"].cluster rect,#chatgpt-mermaid-\_r_52e\_ [data-look="neo"].node polygon{stroke:url(#chatgpt-mermaid-\_r_52e\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_52e\_ [data-look="neo"].swimlane.cluster rect{filter:none;}#chatgpt-mermaid-\_r_52e\_ [data-look="neo"].node path{stroke:url(#chatgpt-mermaid-\_r_52e\_-gradient);stroke-width:1px;}#chatgpt-mermaid-\_r_52e\_ [data-look="neo"].node .outer-path{filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_52e\_ [data-look="neo"].node .neo-line path{stroke:rgb(83, 154, 248);filter:none;}#chatgpt-mermaid-\_r_52e\_ [data-look="neo"].node circle{stroke:url(#chatgpt-mermaid-\_r_52e\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_52e\_ [data-look="neo"].node circle .state-start{fill:#000000;}#chatgpt-mermaid-\_r_52e\_ [data-look="neo"].icon-shape .icon{fill:url(#chatgpt-mermaid-\_r_52e\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_52e\_ [data-look="neo"].icon-shape .icon-neo path{stroke:url(#chatgpt-mermaid-\_r_52e\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_52e\_ .node text{font-size:14px;font-weight:600;letter-spacing:normal;fill:rgb(65, 65, 65);}#chatgpt-mermaid-\_r_52e\_ .edgeLabels text{font-size:13px;font-weight:600;letter-spacing:-0.08px;fill:rgb(65, 65, 65);}#chatgpt-mermaid-\_r_52e\_ .node tspan[font-weight="normal"],#chatgpt-mermaid-\_r_52e\_ .edgeLabels tspan[font-weight="normal"]{font-weight:600;}#chatgpt-mermaid-\_r_52e\_ .edgeLabel .label rect{opacity:1;rx:13px;ry:13px;fill:rgb(252, 252, 252);stroke:rgb(219, 219, 219);stroke-width:1px;}#chatgpt-mermaid-\_r_52e\_ .node rect,#chatgpt-mermaid-\_r_52e\_ .node circle,#chatgpt-mermaid-\_r_52e\_ .node ellipse,#chatgpt-mermaid-\_r_52e\_ .node polygon,#chatgpt-mermaid-\_r_52e\_ .node path{fill:rgb(243, 243, 243);stroke:rgba(0, 0, 0, 0.1);stroke-width:1px;}#chatgpt-mermaid-\_r_52e\_ .node rect{rx:16px;ry:16px;}#chatgpt-mermaid-\_r_52e\_ .mermaid-decision .label-container{fill:rgb(249, 249, 249);stroke:rgb(219, 219, 219);stroke-dasharray:2,2;}#chatgpt-mermaid-\_r_52e\_ .edgePaths .flowchart-link{stroke:rgb(143, 143, 143);stroke-width:1px;stroke-linecap:round;stroke-linejoin:round;}#chatgpt-mermaid-\_r_52e\_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_52e\_ :root{--mermaid-font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";}Load Nemotron trên GPUKiểm tra /ready port 8010Start FastAPI + IngestionWorkerKiểm tra Firebase CloudStart Cloudflare TunnelPublic health checkMở Firebase website để demo

Nên viết hai script:

`start-cloud-demo.sh`

- Kiểm tra CUDA và GPU memory.
- Kiểm tra Nemotron readiness.
- Khởi động FastAPI nếu chưa chạy.
- Khởi động ingestion worker.
- Kiểm tra Firebase Cloud readiness.
- Khởi động Cloudflare connector.
- Kiểm tra public endpoint.
- In trạng thái từng thành phần.

`stop-cloud-demo.sh`

- Dừng các process do script demo tạo.
- Giữ nguyên Firebase Cloud resources.
- Không xóa dữ liệu, PDF hoặc embedding weights.

Lưu ý không tự động kill process chỉ vì chúng đang chiếm port; script nên quản lý PID của chính nó.

### Preflight

Demo preflight checklist

0/12

Máy host có Internet ổn định và cắm nguồn

GPU Nemotron đã load và /ready trả 200

FastAPI /ready trả 200

Ingestion worker đang chạy

Cloudflare Tunnel ở trạng thái Healthy

Firebase website tải được trên máy khác

Tài khoản demo đăng nhập thành công

PDF mẫu đã được ingest và reindex

LLM provider được cấu hình, còn quota

Đã thử một câu hỏi có citation

Không có emulators hoặc secrets bị public

Có phương án backup nếu Tunnel/LLM lỗi

Reset

# 5. Tổng hợp roadmap triển khai

Thời gian là ước lượng công sức kỹ thuật nếu Firebase project, GPU model và quyền truy cập đã sẵn sàng. Không bao gồm thời gian chờ cấp domain certificate hoặc sửa lỗi ngoài dự kiến.

| Phase | Công việc                             | Ưu tiên | Ước lượng |
| ----- | ------------------------------------- | ------- | --------- |
| 0     | Chuẩn hóa demo environment            | P0      | 1–2 giờ   |
| 1     | Firebase Cloud, IAM, indexes, Storage | P0      | 2–4 giờ   |
| 2     | Local API + Worker + Nemotron         | P0      | 1–2 giờ   |
| 3     | Cloudflare Tunnel                     | P0      | 1–2 giờ   |
| 4     | Firebase Hosting                      | P0      | 1–2 giờ   |
| 5     | Authentication + security hardening   | P0      | 4–8 giờ   |
| 6     | GPU contention và performance tests   | P1      | 3–6 giờ   |
| 7     | End-to-end testing                    | P0      | 2–4 giờ   |
| 8     | Startup/stop scripts + runbook        | P1      | 2–3 giờ   |

Dự kiến: khoảng 2–4 ngày làm việc để có bản demo được kiểm thử kỹ, nếu không phát sinh vấn đề nghiêm trọng về authentication hoặc Firebase billing.

## 6. Những file cần thay đổi

| File                                    | Thay đổi đề xuất                                       |
| --------------------------------------- | ------------------------------------------------------ |
| `firebase.json`                         | Thêm Hosting config                                    |
| `apps/web/index.html`                   | API endpoint theo môi trường                           |
| `apps/web/api.js`                       | Cải thiện xử lý lỗi kết nối, timeout                   |
| `apps/api/.env.example`                 | Làm rõ local/demo variables                            |
| `apps/api/app/core/config.py`           | Demo security settings                                 |
| `apps/api/app/api/v1/auth.py`           | Tùy chọn tắt registration                              |
| `apps/api/app/api/v1/embeddings.py`     | Giới hạn quyền truy cập public                         |
| `apps/api/app/api/v1/ai_connections.py` | Bảo vệ local-only OAuth                                |
| `apps/api/app/api/v1/rag.py`            | Bảo đảm public demo không chạy local-only OpenCode     |
| `infra/nginx/api.conf`                  | Sửa upload limit, CORS, rate limiting nếu dùng gateway |
| `scripts/start-cloud-demo.sh`           | Script mới                                             |
| `scripts/stop-cloud-demo.sh`            | Script mới                                             |
| `docs/cloudflare-firebase-demo.md`      | Hướng dẫn deployment và rollback                       |
| `apps/api/tests/`                       | Thêm smoke/integration tests                           |

Không cần viết lại:

- Nemotron inference engine.
- `LocalEmbedding` adapter.
- Pipeline chunking và parsing PDF.
- Firestore vector schema nếu vẫn giữ 1536 chiều.
- Cơ chế embedding profile hiện tại.

## 7. Ba rủi ro lớn nhất cần chốt trước khi triển khai

Rủi ro 1 — Session cookie

Website hoạt động nhưng thầy đăng nhập không được, hoặc đăng nhập xong gọi `/auth/me` lại bị 401.

Cách giải quyết ưu tiên: custom domain cùng site.

Rủi ro 2 — Firebase Emulator khác Firebase Cloud

Local test thành công nhưng website public không có tài liệu, không có user, hoặc upload thất bại.

Cách giải quyết: cloud configuration riêng, deploy indexes, xác nhận Storage billing và tạo dữ liệu demo mới.

Rủi ro 3 — GPU service bị tranh chấp

Thầy upload PDF lớn trong khi đang hỏi đáp; query embedding gặp 429/503.

Cách giải quyết: chuẩn bị tài liệu đã index, giới hạn concurrency, bổ sung bounded queue hoặc retry phù hợp.

## Kết luận kiến trúc

Mình giữ nguyên thiết kế tách biệt `Frontend → Backend → Embedding/Worker → Firebase`, vì phần này đã tương đối hợp lý trong repo.

Thay đổi lớn nhất cho deployment là thêm Cloudflare làm public ingress, chuyển dữ liệu từ Emulator sang Firebase Cloud, rồi xử lý session authentication đúng với domain công khai.

Nếu được chọn, mình sẽ triển khai theo thứ tự:

1. Cloud Firebase + local Nemotron chạy ổn.
2. Cloudflare Tunnel trả API HTTPS.
3. Firebase Hosting gọi API thành công.
4. Authentication và upload PDF chạy end-to-end.
5. Hardening, benchmark và scripts phục vụ demo.

Có một điểm mình cần bạn chốt để chọn chính xác nhánh triển khai:

1\. Bạn có domain riêng để cấu hình qua Cloudflare không?

Có, hoặc có thể mua/thiết lập domain riêng

Không, chỉ muốn dùng `*.web.app`

2\. Model sinh câu trả lời hiện tại của bạn chạy theo hướng nào?

LLM API key trực tiếp (OpenAI/Anthropic...)

Local OpenCode / ChatGPT OAuth

Chưa chốt, muốn xem phương án tối ưu

Chốt kiến trúc và triển khai tiếp&#x20;

Hai lựa chọn này ảnh hưởng trực tiếp tới phần authentication và API security, nên cần xác định trước khi bắt đầu sửa code.