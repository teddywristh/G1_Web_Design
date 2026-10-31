# Legal AI Assistant — Project Guide

Tài liệu này là hướng dẫn chung cho thành viên mới, frontend agent, backend
agent, AI/RAG agent và database/devops agent.

## 1. Tổng quan hệ thống

Legal AI Assistant hỗ trợ:

- Tìm kiếm văn bản pháp luật.
- Đặt câu hỏi về luật, nghị định, thông tư và văn bản liên quan.
- Trả lời bằng AI dựa trên tài liệu pháp luật.
- Hiển thị nguồn trích dẫn có thể kiểm tra.
- Lưu lịch sử hội thoại và tin nhắn.
- Cho phép Admin upload, quản lý và theo dõi trạng thái xử lý tài liệu PDF.

Kiến trúc MVP:

```text
Frontend (Next.js)
        |
        | REST + Firebase ID Token
        v
Backend (FastAPI)
   |              |                 |
   v              v                 v
Firebase Auth  Firestore       Firebase Storage
                              |
                              v
                         PDF pháp luật

AI/RAG: đọc PDF -> chunk -> embedding -> ChromaDB -> LLM
```

Firebase Admin SDK chỉ được dùng ở backend. Frontend không được dùng Admin SDK
hoặc chứa service-account credentials.

## 2. Các chức năng chính

### 2.1. Authentication và authorization

- Firebase Authentication quản lý danh tính người dùng.
- Frontend đăng nhập bằng Firebase Client SDK.
- Frontend gửi token qua header:

```http
Authorization: Bearer <FIREBASE_ID_TOKEN>
```

- Backend xác minh token bằng Firebase Admin SDK.
- UID lấy từ token là nguồn định danh đáng tin cậy.
- Role phải được đọc từ server-side profile, không tin role do frontend gửi.
- Role MVP: `user` và `admin`.

### 2.2. Firestore

Các collection chính:

- `users/{uid}`: profile và role.
- `documents/{documentId}`: metadata pháp luật và trạng thái xử lý.
- `conversations/{conversationId}`: hội thoại của user.
- `messages/{messageId}` hoặc messages theo conversation: câu hỏi, câu trả lời, citations.
- `document_chunks/{chunkId}`: metadata chunk và vector ID.
- `processing_jobs/{jobId}`: tiến trình xử lý tài liệu.

Schema marker có thể được bootstrap bằng:

```powershell
python scripts/bootstrap_legal_ai_firestore.py --apply
```

Script chỉ tạo document `_schema`, không ghi đè dữ liệu hiện có.

### 2.3. Firebase Storage

Các file PDF được lưu trong Storage, còn Firestore chỉ lưu `storagePath`.

Service chính:

[firebase_storage.py](../apps/api/app/services/firebase_storage.py)

Hỗ trợ:

- Upload file.
- Download file.
- Delete file.
- Kết nối Storage Emulator bằng `STORAGE_EMULATOR_HOST`.
- Dùng anonymous credentials cho Emulator.
- Dùng ADC hoặc Workload Identity trong production.

### 2.4. Luồng upload tài liệu

```text
Admin đăng nhập
    -> Frontend gửi PDF + ID token
    -> Backend verify token và role admin
    -> Upload PDF vào Firebase Storage
    -> Tạo metadata trong Firestore
    -> AI service xử lý PDF
    -> Cập nhật processingStatus
```

Các trạng thái nên dùng:

```text
uploaded -> processing -> ready
                    \-> failed
```

### 2.5. Luồng hỏi đáp

```text
User question
    -> Backend verify Firebase ID token
    -> Load conversation
    -> Retrieve relevant chunks từ ChromaDB
    -> Gọi LLM
    -> Tạo câu trả lời + citations
    -> Lưu message
    -> Trả response cho frontend
```

Citation phải chứa định danh tài liệu và vị trí nguồn, ví dụ:

```json
{
  "documentId": "law_001",
  "documentTitle": "Luật Doanh nghiệp",
  "article": "Điều 8",
  "clause": "Khoản 2",
  "page": 12,
  "chunkId": "chunk_001"
}
```

## 3. Setup cơ bản sau khi clone repo

### 3.1. Yêu cầu môi trường

- Git.
- Node.js 20 trở lên.
- Java để chạy Firebase Emulator Suite.
- Python 3.11 trở lên.
- Firebase CLI.

Kiểm tra:

```powershell
node --version
java -version
firebase --version
python --version
```

### 3.2. Cài Python environment

Từ thư mục project:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Nếu PowerShell chặn activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Có thể bỏ qua activation và dùng trực tiếp:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3.3. Cấu hình Firebase local

Copy file môi trường:

```powershell
Copy-Item .env.example .env
```

Khi chạy Emulator, `apps/api/.env` cần có:

```env
APP_ENV=development
FIREBASE_PROJECT_ID=demo-legal-ai
FIREBASE_STORAGE_BUCKET=demo-legal-ai.appspot.com
FIRESTORE_EMULATOR_HOST=127.0.0.1:8081
STORAGE_EMULATOR_HOST=http://127.0.0.1:9198
```

Không commit `.env`, service-account JSON hoặc API keys.

### 3.4. Chạy Firebase Emulator

Từ thư mục root:

```powershell
firebase emulators:start --only firestore,storage --project demo-legal-ai
```

Cấu hình hiện tại:

| Service | Host | Port |
|---|---|---:|
| Firestore | `127.0.0.1` | `8081` |
| Storage | `127.0.0.1` | `9198` |
| Emulator UI | disabled | - |

Project bắt đầu bằng `demo-` chỉ dùng cho local Emulator; không tìm project
này trong Firebase Console.

### 3.5. Chạy backend

```powershell
cd apps/api
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

### 3.6. Chạy test

Từ root:

```powershell
python -m pytest apps/api/tests -v
```

Test Storage cần Storage Emulator đang chạy:

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m pytest tests/test_firebase_storage.py -v
```

Nếu Windows có lỗi quyền với thư mục tạm của pytest:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_firebase_storage.py -v `
  --basetemp .pytest-run-local -p no:cacheprovider
```

## 4. Sử dụng Firebase project thật

Project Development hiện tại:

```text
legal-ai-dev-aeb51
```

Kiểm tra project và database:

```powershell
firebase use legal-ai-dev-aeb51
firebase firestore:databases:list --project legal-ai-dev-aeb51
```

Project thật có Firestore database `(default)`, Standard edition, tại
`asia-southeast1`.

Để backend Python truy cập cloud, cần Application Default Credentials:

```powershell
gcloud auth application-default login
```

Không dùng `demo-legal-ai` hoặc các biến `*_EMULATOR_HOST` khi chạy production.
Bootstrap schema cloud:

```powershell
python scripts/bootstrap_legal_ai_firestore.py --apply
```

Chỉ chạy lệnh này sau khi xác nhận project và credentials đúng.

## 5. Hướng dẫn frontend agent

Frontend dùng Next.js và Firebase Client SDK.

Frontend agent cần:

1. Đọc `docs/architecture.md`, `docs/plans.md` và tài liệu này.
2. Tạo `.env.local` từ `apps/web/.env.example`.
3. Chỉ dùng biến client bắt đầu bằng `NEXT_PUBLIC_`.
4. Cấu hình Firebase Client SDK bằng web app config của project.
5. Đăng nhập user bằng Firebase Authentication.
6. Lấy ID token sau khi đăng nhập.
7. Gửi token đến FastAPI trong header `Authorization`.
8. Không đọc trực tiếp private Firestore/Storage nếu API là data boundary.
9. Hiển thị citation từ response và cho phép user kiểm tra nguồn.
10. Không lưu service account, private key hoặc Admin SDK trong frontend.

Ví dụ request frontend đến backend:

```ts
const token = await currentUser.getIdToken();

await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/chat`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  },
  body: JSON.stringify({ conversationId, question }),
});
```

## 6. Hướng dẫn backend agent

- Route không truy cập Firestore trực tiếp.
- Dùng repository trong `apps/api/app/repositories/`.
- Verify Firebase ID Token trước route protected.
- Kiểm tra quyền trên server.
- Dùng pagination cho list query.
- Dùng Firestore server timestamps.
- Không trả credentials hoặc dữ liệu nhạy cảm.
- Viết unit test cho repository và integration test cho auth/storage.

Khi thêm API mới, cập nhật API contract và thông báo cho frontend agent.

## 7. Hướng dẫn AI/RAG agent

- Đọc PDF từ Firebase Storage bằng `storagePath`.
- Không lưu PDF gốc trong ChromaDB.
- Mỗi chunk phải gắn `documentId`, `chunkId`, page/article nếu có.
- Lưu vector ID vào metadata Firestore hoặc processing job.
- Cập nhật trạng thái xử lý rõ ràng: `uploaded`, `processing`, `ready`, `failed`.
- Câu trả lời phải kèm citations có thể truy ngược về tài liệu gốc.

## 8. Hướng dẫn database/devops agent

- Duy trì project dev và production tách biệt.
- Giữ credentials ngoài Git.
- Ưu tiên Emulator cho development và test.
- Kiểm tra rules/indexes trước khi deploy.
- Theo dõi giới hạn reads/writes và dung lượng Storage.
- Không tự ý đổi schema/API contract mà không thông báo backend agent.
- Giữ CI chạy compile, unit test và integration test phù hợp.

Các file hạ tầng chính:

- `firebase.json`: Emulator và Firebase resource configuration.
- `infra/firebase/firestore.rules`: Firestore Security Rules.
- `infra/firebase/storage.rules`: Storage Security Rules.
- `infra/firebase/firestore.indexes.json`: composite indexes.
- `.github/workflows/backend-ci.yml`: backend CI.
- `scripts/bootstrap_legal_ai_firestore.py`: schema marker bootstrap.

## 9. Quy trình làm việc cho mọi agent

### Trước khi code

1. Đọc `README.md`, `docs/architecture.md`, `docs/plans.md`.
2. Kiểm tra `git status` và branch hiện tại.
3. Xác định file/ownership liên quan.
4. Không ghi đè thay đổi của agent khác.
5. Kiểm tra API contract và schema hiện có.

### Trong khi code

1. Thay đổi nhỏ, đúng phạm vi.
2. Dùng environment variables.
3. Viết test cùng với code.
4. Cập nhật tài liệu khi thay đổi behavior.
5. Không commit secrets hoặc file local.

### Trước khi bàn giao

```powershell
git diff --check
python -m compileall apps/api/app
python -m pytest apps/api/tests -v
git status
```

Commit message nên dùng:

```text
feat(auth): verify Firebase ID tokens
feat(storage): add PDF storage service
feat(database): add Firestore repository
test(storage): cover emulator upload flow
docs(setup): document local development
```

Bàn giao cần ghi rõ:

- Đã thay đổi file nào.
- Test nào đã chạy.
- Environment nào đã dùng.
- Schema/API contract nào thay đổi.
- Known issue và bước tiếp theo.

## 10. Bảo mật bắt buộc

- Không commit `.env`, `.env.local`, service-account JSON, private key hoặc LLM API key.
- Không đưa Firebase Admin SDK vào frontend.
- Không tin role từ request body.
- Không public toàn bộ Storage bucket.
- Không dùng project production để test dữ liệu giả.
- Không chạy bootstrap cloud nếu chưa xác nhận project ID và credentials.
