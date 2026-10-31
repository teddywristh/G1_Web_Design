# LEGAL AI SYSTEM
## Implementation Plan for AI Agents
### Focus: Database, DevOps & Infrastructure

**Project:** Legal AI Assistant  
**Architecture direction:** Firebase-first, API-based, RAG-ready  
**Target:** MVP development by a 4-member team  
**Document version:** 1.0

---

# 1. Project Objective

Xây dựng hệ thống Legal AI Assistant cho phép người dùng:

1. Tìm kiếm văn bản pháp luật.
2. Đặt câu hỏi về luật, nghị định, thông tư và các văn bản liên quan.
3. Nhận câu trả lời từ AI dựa trên tài liệu pháp luật.
4. Xem nguồn trích dẫn của câu trả lời.
5. Lưu lịch sử hội thoại.
6. Quản lý tài liệu pháp luật ở phía Admin.

## 1.1. Technical objectives

- Sử dụng Firebase để giảm công việc quản trị database.
- Không triển khai các dịch vụ hạ tầng phức tạp nếu MVP chưa cần.
- Tách biệt frontend, backend và AI processing.
- Thiết kế database có khả năng mở rộng.
- Có môi trường Development và Production riêng biệt.
- Có backup, logging và security rules cơ bản.
- Đảm bảo AI có thể truy xuất đúng tài liệu và nguồn trích dẫn.

---

# 2. Recommended Architecture

## 2.1. Technology stack

| Component | Recommended technology | Responsibility |
|---|---|---|
| Frontend | Next.js + TypeScript | User interface |
| Backend | FastAPI + Python | API and business logic |
| Authentication | Firebase Authentication | User login and identity |
| Main database | Cloud Firestore | Users, documents, conversations |
| File storage | Firebase Storage | PDF and legal documents |
| AI / RAG | Python + LangChain or custom pipeline | Retrieval and generation |
| Vector retrieval | ChromaDB for initial MVP | Embedding search |
| Deployment | Vercel + Google Cloud Run | Frontend and backend |
| CI/CD | GitHub Actions | Automated testing and deployment |
| Monitoring | Firebase Console + Cloud Logging | Errors and system monitoring |

**Important architectural decision:**

Không sử dụng PostgreSQL, Redis và pgvector ngay từ đầu.

MVP sử dụng:

- Firebase Authentication: xác thực người dùng.
- Firestore: database chính.
- Firebase Storage: lưu file.
- ChromaDB: vector retrieval cho RAG trong giai đoạn đầu.
- FastAPI: xử lý nghiệp vụ và điều phối AI.

Khi hệ thống có nhu cầu lớn hơn, có thể chuyển vector retrieval sang Vertex AI Vector Search hoặc PostgreSQL + pgvector.

## 2.2. System architecture

```text
                  USER
                    |
                    v
             NEXT.JS FRONTEND
                    |
                    v
              FASTAPI BACKEND
                    |
          +---------+----------+
          |         |          |
          v         v          v
      FIREBASE   FIRESTORE   AI / RAG
        AUTH       DB           |
          |         |           v
          |         |        CHROMA
          |         |           |
          |         |           v
          |         |       LLM API
          |         |
          v         v
       IDENTITY   DATA
                    |
                    v
              FIREBASE STORAGE
                    |
                    v
             LEGAL PDF FILES
```

### Architecture rules

1. Frontend không được truy cập database bằng Admin SDK.
2. Backend là nơi xử lý các thao tác nghiệp vụ quan trọng.
3. Firebase Authentication chịu trách nhiệm xác thực.
4. FastAPI xác minh Firebase ID Token trước khi xử lý API.
5. Firestore lưu metadata và dữ liệu nghiệp vụ.
6. Firebase Storage lưu file PDF gốc.
7. ChromaDB lưu embeddings và metadata phục vụ truy xuất.
8. API key và service account không được đưa vào frontend.

---

# 3. Database Design

## 3.1. Database responsibilities

### Firebase Authentication

Lưu và quản lý:

- User identity.
- Email/password authentication.
- Google authentication nếu cần.
- UID.
- Authentication state.

Không tự tạo hệ thống lưu mật khẩu trong Firestore.

### Cloud Firestore

Lưu:

- User profiles.
- Legal document metadata.
- Conversations.
- Messages.
- Document processing status.
- User feedback.
- Administrative metadata.

### Firebase Storage

Lưu:

- Original PDF files.
- Processed document files nếu cần.
- File metadata có liên quan.

### ChromaDB

Lưu:

- Document chunks.
- Embeddings.
- Chunk metadata.
- Document identifiers.

Không lưu bản PDF gốc trong ChromaDB.

## 3.2. Firestore collection structure

Đề xuất cấu trúc:

```text
legal-ai/
│
├── users/
│   └── {uid}
│       ├── email
│       ├── displayName
│       ├── role
│       ├── createdAt
│       └── isActive
│
├── legal_documents/
│   └── {documentId}
│       ├── title
│       ├── documentNumber
│       ├── documentType
│       ├── issuingAuthority
│       ├── issueDate
│       ├── effectiveDate
│       ├── status
│       ├── storagePath
│       ├── processingStatus
│       ├── chunkCount
│       └── createdAt
│
├── conversations/
│   └── {conversationId}
│       ├── userId
│       ├── title
│       ├── createdAt
│       ├── updatedAt
│       └── status
│
├── conversations/{conversationId}/messages/
│   └── {messageId}
│       ├── role
│       ├── content
│       ├── citations
│       ├── createdAt
│       └── feedback
│
└── system_logs/
    └── {logId}
        ├── event
        ├── actorId
        ├── status
        └── createdAt
```

### Data design notes

**users**

- Document ID phải trùng Firebase Authentication UID.
- `role` có thể là `user`, `admin`.
- Không cho client tự sửa role.

**legal_documents**

- `documentId` là ID nội bộ.
- `documentNumber` là số hiệu văn bản pháp luật.
- `storagePath` lưu đường dẫn file trong Firebase Storage.
- `processingStatus` gồm `pending`, `processing`, `completed`, `failed`.

**conversations**

- Một user có nhiều conversations.
- Mỗi conversation có nhiều messages.
- Không nên lưu toàn bộ messages trong một document duy nhất vì giới hạn kích thước document của Firestore.

**messages**

- Lưu câu hỏi, câu trả lời và citations.
- Citations phải chứa ID văn bản và thông tin định vị nguồn.
- Không chỉ lưu tên tài liệu dưới dạng text.

Ví dụ citation:

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

## 3.3. Firestore indexes

Agent cần kiểm tra và tạo composite indexes cho những truy vấn chính:

| Collection | Fields | Purpose |
|---|---|---|
| conversations | userId + updatedAt | User conversation history |
| legal_documents | status + effectiveDate | Filter legal documents |
| legal_documents | documentType + issueDate | Search by document type |
| system_logs | event + createdAt | Admin monitoring |

Chỉ tạo index khi truy vấn thực tế yêu cầu. Không tạo index tùy tiện.

## 3.4. Storage structure

```text
legal-ai-storage/
│
├── legal-documents/
│   ├── laws/
│   ├── decrees/
│   ├── circulars/
│   └── resolutions/
│
├── temporary/
│
└── exports/
```

Quy tắc:

- File PDF gốc được lưu trong `legal-documents/`.
- Firestore chỉ lưu `storagePath`.
- Không lưu file lớn dưới dạng Base64 trong Firestore.
- Chỉ Admin được upload hoặc xóa tài liệu pháp luật.
- Backend kiểm tra loại file, kích thước và quyền trước khi upload.
- Không công khai toàn bộ Storage bucket.

---

# 4. Role Assignment: Database & DevOps Agent

Đây là phần công việc trọng tâm dành cho thành viên phụ trách Database & DevOps.

## 4.1. Mission

Agent chịu trách nhiệm:

1. Khởi tạo Firebase project.
2. Cấu hình Firebase Authentication.
3. Thiết kế Firestore collections.
4. Thiết lập Firebase Storage.
5. Thiết lập security rules.
6. Tạo môi trường Development và Production.
7. Cấu hình backend credentials.
8. Thiết lập Docker.
9. Thiết lập GitHub Actions.
10. Kiểm thử database và deployment.
11. Viết tài liệu hướng dẫn thành viên khác sử dụng infrastructure.

Agent không tự ý thay đổi API contract hoặc database schema mà không thông báo Backend Agent.

## 4.2. Phase 1: Environment preparation

### Task 1. Create Firebase project

Thực hiện:

1. Truy cập Firebase Console.
2. Tạo project `legal-ai-dev`.
3. Enable Google Analytics nếu thực sự cần.
4. Tạo Firestore Database.
5. Tạo Firebase Authentication.
6. Tạo Firebase Storage.
7. Tạo service account cho backend.

Tạo project Production riêng khi chuẩn bị release.

**Deliverables:**

```text
docs/
└── infrastructure/
    ├── firebase-setup.md
    └── environment-variables.md
```

**Acceptance criteria:**

- Firebase project hoạt động.
- Firestore có thể đọc/ghi bằng backend.
- Authentication được enable.
- Storage có thể upload/download bằng backend.
- Credentials không được commit lên GitHub.

## 4.3. Phase 2: Firebase SDK integration

### Task 2. Backend Firebase initialization

Cài đặt:

```bash
pip install firebase-admin
```

Tạo cấu trúc:

```text
backend/
├── app/
│   ├── core/
│   │   ├── config.py
│   │   └── firebase.py
│   │
│   ├── services/
│   │   ├── firestore_service.py
│   │   └── storage_service.py
│   │
│   └── main.py
│
├── tests/
├── requirements.txt
└── .env.example
```

Tạo `firebase.py`:

```python
import firebase_admin
from firebase_admin import credentials, firestore, storage

def initialize_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(
            "path/to/service-account.json"
        )

        firebase_admin.initialize_app(
            cred,
            {
                "storageBucket": "YOUR_BUCKET_NAME"
            }
        )

    return {
        "db": firestore.client(),
        "storage": storage.bucket()
    }
```

**Important:**

Đây là ví dụ khởi tạo cho local development.

Trong Production, ưu tiên Application Default Credentials hoặc workload identity thay vì lưu service account JSON trực tiếp trên server.

### Task 3. Environment variables

Tạo `.env.example`:

```env
APP_ENV=development
APP_NAME=legal-ai

FIREBASE_PROJECT_ID=
FIREBASE_STORAGE_BUCKET=

GOOGLE_APPLICATION_CREDENTIALS=

FIREBASE_AUTH_EMULATOR_HOST=
FIRESTORE_EMULATOR_HOST=

LLM_API_KEY=
```

Không commit `.env` hoặc service account JSON.

**Acceptance criteria:**

- Backend khởi tạo Firebase thành công.
- Backend kết nối Firestore.
- Backend có thể upload file thử nghiệm.
- Có hướng dẫn cấu hình môi trường cho developer mới.

## 4.4. Phase 3: Database implementation

### Task 4. Implement Firestore repositories

Không để các API route truy cập Firestore trực tiếp.

Tạo repository layer:

```text
app/
├── repositories/
│   ├── user_repository.py
│   ├── document_repository.py
│   ├── conversation_repository.py
│   └── message_repository.py
```

Ví dụ:

```python
class DocumentRepository:

    def __init__(self, db):
        self.collection = db.collection(
            "legal_documents"
        )

    def create(self, document_id, data):
        self.collection.document(
            document_id
        ).set(data)

    def get_by_id(self, document_id):
        doc = self.collection.document(
            document_id
        ).get()

        if not doc.exists:
            return None

        return doc.to_dict()
```

Các repository cần hỗ trợ:

| Repository | Required operations |
|---|---|
| UserRepository | Create, get, update |
| DocumentRepository | Create, get, update, list |
| ConversationRepository | Create, get, list, update, delete |
| MessageRepository | Create, list, get |

Lưu ý:

- Phân trang bằng cursor.
- Không tải toàn bộ collection.
- Dùng server timestamps.
- Xử lý trường hợp document không tồn tại.
- Không ghi đè dữ liệu ngoài ý muốn.
- Các thao tác liên quan nhiều document phải đánh giá nhu cầu transaction.

### Task 5. Implement Storage service

Các chức năng:

- Upload PDF.
- Download PDF.
- Delete PDF.
- Generate signed URL nếu cần.
- Kiểm tra file size.
- Kiểm tra MIME type.

Ví dụ:

```python
def upload_pdf(bucket, file_path, destination):
    blob = bucket.blob(destination)

    blob.upload_from_filename(
        file_path,
        content_type="application/pdf"
    )

    return destination
```

Không lưu public URL cố định cho file riêng tư nếu không cần thiết. Lưu storage path và cấp quyền truy cập qua backend.

## 4.5. Phase 4: Authentication and authorization

### Task 6. Verify Firebase ID Token

Frontend sử dụng Firebase Client SDK để đăng nhập.

Sau khi đăng nhập, frontend gửi Firebase ID Token:

```http
Authorization: Bearer <FIREBASE_ID_TOKEN>
```

Backend xác minh token:

```python
from firebase_admin import auth
from fastapi import Header, HTTPException

def verify_firebase_token(
    authorization: str = Header(...)
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    token = authorization.split(" ", 1)[1]

    try:
        return auth.verify_id_token(token)

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
```

Sau khi xác minh, backend lấy UID từ token và sử dụng UID để kiểm tra quyền truy cập.

### Task 7. Role-based access control

Roles:

```text
USER
ADMIN
```

Permissions:

| Action | User | Admin |
|---|---|---|
| Ask legal questions | Yes | Yes |
| View own conversations | Yes | Yes |
| Delete own conversations | Yes | Yes |
| View legal documents | Yes | Yes |
| Upload legal documents | No | Yes |
| Delete legal documents | No | Yes |
| Manage users | No | Yes |

Không tin tưởng role được gửi từ frontend.

Backend phải lấy role từ dữ liệu đáng tin cậy và kiểm tra quyền trên server.

---

# 5. Security Rules

## 5.1. Firestore security

Với kiến trúc backend sử dụng Firebase Admin SDK:

- Firestore Security Rules không thay thế authorization của backend.
- Firebase Admin SDK có quyền bỏ qua Firestore Security Rules.
- Vì vậy backend phải tự xác minh UID và quyền trước khi đọc/ghi.
- Client không được truy cập trực tiếp những dữ liệu nhạy cảm.

Ví dụ rule giới hạn truy cập client:

```javascript
rules_version = '2';

service cloud.firestore {
  match /databases/{database}/documents {

    match /users/{userId} {
      allow read, write: if false;
    }

    match /legal_documents/{documentId} {
      allow read, write: if false;
    }

    match /conversations/{conversationId} {
      allow read, write: if false;
    }

    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

Nếu frontend cần truy cập trực tiếp một collection cụ thể, hãy thiết kế rule riêng theo UID và kiểm thử bằng Firebase Emulator.

## 5.2. Storage security

- Chỉ Admin được upload tài liệu.
- Không cho phép upload file tùy ý.
- Giới hạn dung lượng.
- Kiểm tra MIME type.
- Không cho phép truy cập file riêng tư không xác thực.

---

# 6. DevOps Implementation

## 6.1. Repository structure

Đề xuất monorepo:

```text
legal-ai/
│
├── frontend/
│
├── backend/
│
├── ai/
│
├── infrastructure/
│   ├── docker/
│   ├── firebase/
│   └── scripts/
│
├── docs/
│   ├── architecture.md
│   ├── database-schema.md
│   ├── api-contract.md
│   └── deployment.md
│
├── .github/
│   └── workflows/
│       ├── backend-ci.yml
│       └── frontend-ci.yml
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

## 6.2. Docker setup

Mục tiêu:

- Developer có thể khởi động backend bằng Docker.
- AI service có môi trường riêng.
- ChromaDB chạy local trong development.
- Không bắt buộc chạy Firebase bằng Docker vì Firebase Emulator Suite đã có công cụ riêng.

Ví dụ `docker-compose.yml`:

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8001:8000"
    env_file:
      - .env
    depends_on:
      - chroma

  chroma:
    image: chromadb/chroma
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma

volumes:
  chroma_data:
```

Lưu ý: nếu backend và Chroma chạy trong cùng Docker network, backend kết nối tới `http://chroma:8000`, không dùng `localhost`.

## 6.3. Firebase Emulator Suite

Dùng Firebase Emulator để phát triển và kiểm thử local.

Cài đặt Firebase CLI:

```bash
npm install -g firebase-tools
```

Đăng nhập:

```bash
firebase login
```

Khởi tạo:

```bash
firebase init emulators
```

Chọn:

- Authentication Emulator
- Firestore Emulator
- Storage Emulator

Khởi chạy:

```bash
firebase emulators:start
```

Lợi ích:

- Không ghi dữ liệu thử nghiệm vào Production.
- Không tiêu tốn quota Production khi test.
- Có thể kiểm tra security rules.
- Thành viên có môi trường phát triển nhất quán.

## 6.4. GitHub Actions CI

Tạo workflow:

```yaml
name: Backend CI

on:
  push:
    paths:
      - "backend/**"
  pull_request:
    paths:
      - "backend/**"

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt

      - name: Run tests
        run: |
          pytest backend/tests
```

Bổ sung các bước lint, type checking và integration tests khi dự án ổn định.

Không đưa Firebase service account hoặc LLM API key vào workflow dưới dạng plaintext.

## 6.5. Deployment strategy

| Component | MVP deployment |
|---|---|
| Frontend | Vercel |
| Backend | Google Cloud Run |
| Authentication | Firebase |
| Firestore | Firebase |
| File storage | Firebase Storage |
| ChromaDB | Local development first; persistent hosted service when needed |

Không deploy ChromaDB trên container ephemeral mà không có persistent storage.

---

# 7. Database Testing Plan

## 7.1. Unit tests

Test từng repository:

- Create document.
- Get document.
- Update document.
- Delete document.
- Query documents.
- Create conversation.
- Add message.
- Retrieve conversation history.

## 7.2. Integration tests

Test các luồng:

1. User đăng nhập.
2. Backend xác minh Firebase token.
3. User tạo conversation.
4. User gửi message.
5. Backend lưu message.
6. Backend lấy lịch sử conversation.
7. Admin upload PDF.
8. Backend tạo metadata trong Firestore.
9. Backend lưu PDF trong Storage.

## 7.3. Security tests

Kiểm tra:

- User A không đọc được conversation của User B.
- User không thể upload tài liệu.
- User không thể tự đổi role thành Admin.
- Request không có token bị từ chối.
- Token hết hạn bị từ chối.
- File không phải PDF bị từ chối.
- Backend không trả về dữ liệu nhạy cảm.

## 7.4. Acceptance criteria

| Criteria | Expected result |
|---|---|
| Firebase connection | Pass |
| User authentication | Pass |
| Firestore CRUD | Pass |
| Storage upload/download | Pass |
| User isolation | Pass |
| Admin permissions | Pass |
| Repository tests | Pass |
| Docker startup | Pass |
| CI pipeline | Pass |
| Deployment smoke test | Pass |

---

# 8. Execution Schedule

Dự kiến 7 ngày làm việc cho Database & DevOps Agent.

| Day | Tasks | Deliverables |
|---|---|---|
| Day 1 | Firebase setup, project structure | Firebase dev project |
| Day 2 | Firestore schema, Storage structure | Database schema document |
| Day 3 | Firebase Admin SDK, repositories | Working database layer |
| Day 4 | Authentication, authorization, rules | Auth integration |
| Day 5 | Docker, Emulator, local environment | Reproducible development |
| Day 6 | CI, integration and security tests | Automated test pipeline |
| Day 7 | Deployment, documentation, handover | MVP infrastructure |

---

# 9. Agent Working Instructions

## 9.1. Before implementation

Agent must:

1. Read the project README.
2. Read architecture documentation.
3. Read API contracts.
4. Check the existing repository structure.
5. Identify existing Firebase configuration.
6. Check current branches and avoid overwriting other members' work.
7. Report missing requirements before making assumptions.

Không tự ý tạo lại project hoặc thay đổi stack nếu repository đã có cấu trúc tương ứng.

## 9.2. During implementation

Agent must:

1. Implement one task at a time.
2. Keep changes isolated.
3. Write tests for each repository.
4. Use environment variables.
5. Avoid hardcoded credentials.
6. Update documentation.
7. Report any schema changes to Backend and Frontend Agents.
8. Commit changes with clear messages.

Commit convention:

```text
feat(database): initialize firestore repositories
feat(auth): verify firebase id tokens
feat(storage): implement pdf upload service
chore(devops): configure docker environment
ci: add backend test workflow
docs(database): document firestore schema
```

## 9.3. After implementation

Agent must provide:

- List of completed tasks.
- List of changed files.
- Database schema.
- Firebase setup instructions.
- Environment variable documentation.
- Test results.
- Deployment instructions.
- Known issues.
- Remaining tasks.

## 9.4. Definition of Done

Một task chỉ được đánh dấu Done khi:

- Code đã được implement.
- Test đã chạy thành công.
- Không chứa secret.
- Có xử lý lỗi.
- Documentation đã được cập nhật.
- Không phá vỡ API contract.
- Pull Request đã được tạo và review.

---

# 10. Team Integration Contract

Database & DevOps Agent không làm việc độc lập. Cần thống nhất contract với 3 thành viên còn lại.

| Team member | Needs from Database & DevOps |
|---|---|
| Frontend Agent | Firebase client config, Auth flow, API base URL |
| Backend Agent | Firebase Admin initialization, repositories, schema, Storage service |
| AI Agent | PDF storage path, document ID, processing status, metadata |
| Database & DevOps Agent | Infrastructure, environment, security, CI/CD |

### Critical integration flow: Upload legal document

```text
ADMIN
  |
  v
FRONTEND
  |
  v
FASTAPI
  |
  +----> VERIFY ADMIN TOKEN
  |
  +----> UPLOAD PDF TO STORAGE
  |
  +----> CREATE DOCUMENT METADATA
  |
  v
AI PROCESSING
  |
  +----> EXTRACT TEXT
  |
  +----> CHUNK DOCUMENT
  |
  +----> GENERATE EMBEDDINGS
  |
  +----> SAVE TO CHROMA
  |
  v
UPDATE FIRESTORE STATUS
  |
  v
COMPLETED
```

### Critical integration flow: Ask legal question

```text
USER
  |
  v
FRONTEND
  |
  v
FASTAPI
  |
  +----> VERIFY USER TOKEN
  |
  +----> LOAD CONVERSATION
  |
  +----> RETRIEVE DOCUMENT CHUNKS
  |
  +----> CALL LLM
  |
  +----> SAVE MESSAGE AND CITATIONS
  |
  v
RETURN ANSWER
```

---

# 11. Important Technical Decisions

## 11.1. Why Firebase instead of PostgreSQL?

For the first MVP:

- Không cần quản lý database server.
- Không cần tự thiết lập backup server.
- Authentication tích hợp sẵn.
- Storage tích hợp sẵn.
- Có Emulator cho local development.
- Dễ chia sẻ cấu hình giữa các thành viên.
- Có thể triển khai nhanh.

## 11.2. Firebase limitations

Firestore là NoSQL database, không phải relational database.

Cần chú ý:

- Không có JOIN như SQL.
- Cần thiết kế document structure ngay từ đầu.
- Query phức tạp có thể cần denormalization.
- Có giới hạn về kích thước document và số lần đọc/ghi.
- Chi phí có thể tăng theo lượng reads/writes.
- Không nên dùng Firestore để thay thế hoàn toàn một relational database cho các báo cáo phức tạp.

Đối với Legal AI, metadata và conversation history có thể dùng Firestore tốt trong MVP. Nếu sau này cần truy vấn quan hệ pháp luật phức tạp, báo cáo lớn hoặc transaction nhiều bảng, hãy cân nhắc PostgreSQL.

## 11.3. Why ChromaDB is separate?

Firestore lưu dữ liệu nghiệp vụ. ChromaDB phục vụ vector retrieval.

Không nên cố gắng biến một database thành công cụ giải quyết mọi loại truy vấn.

Giai đoạn MVP có thể sử dụng ChromaDB để chứng minh RAG hoạt động trước. Khi có yêu cầu production rõ ràng, đánh giá dịch vụ vector database phù hợp hơn.

## 11.4. Cost control

Agent cần:

- Thiết lập budget alerts trong Google Cloud.
- Theo dõi Firestore reads/writes.
- Giới hạn dung lượng file upload.
- Tránh đọc toàn bộ collection.
- Sử dụng pagination.
- Không bật dịch vụ chưa cần thiết.
- Tách project dev và production.
- Theo dõi chi phí LLM API.

---

# 12. First Sprint Checklist

## Database & DevOps Agent

- [ ] Tạo Firebase project Development.
- [ ] Enable Firebase Authentication.
- [ ] Enable Firestore.
- [ ] Enable Firebase Storage.
- [ ] Tạo service account hoặc cấu hình ADC.
- [ ] Thiết kế Firestore schema.
- [ ] Viết database-schema.md.
- [ ] Implement Firebase initialization.
- [ ] Implement repositories.
- [ ] Implement Storage service.
- [ ] Implement token verification.
- [ ] Configure security rules.
- [ ] Configure Firebase Emulator.
- [ ] Create Docker Compose.
- [ ] Create GitHub Actions.
- [ ] Write integration tests.
- [ ] Document deployment.
- [ ] Handover to other agents.

## MVP Infrastructure Completion

Hạ tầng được xem là sẵn sàng khi:

1. Frontend có thể đăng nhập.
2. Backend xác minh được user token.
3. Backend lưu và truy xuất dữ liệu Firestore.
4. Admin upload được PDF.
5. PDF được lưu trong Firebase Storage.
6. AI Agent nhận được document ID và storage path.
7. Conversation và messages được lưu thành công.
8. User chỉ truy cập được dữ liệu của mình.
9. Local environment có thể chạy theo README.
10. CI pipeline kiểm tra code tự động.

---

# 13. Recommended Implementation Priority

**Không triển khai tất cả cùng lúc.**

Ưu tiên theo thứ tự:

1. Firebase project + Firestore.
2. Firebase Authentication.
3. Backend Firebase integration.
4. User and conversation repositories.
5. Firebase Storage.
6. Legal document metadata.
7. AI document processing integration.
8. Docker and local emulator.
9. Automated tests.
10. CI/CD and production deployment.

**Final recommendation:** Đối với MVP, hãy giữ hệ thống ở mức Firebase Authentication + Firestore + Firebase Storage + FastAPI + ChromaDB. Chỉ bổ sung PostgreSQL, Redis hoặc managed vector database khi có yêu cầu cụ thể chứng minh rằng kiến trúc hiện tại không còn đáp ứng được.

Đây là cách giảm gánh nặng DevOps để team tập trung vào tính năng cốt lõi: tìm kiếm pháp luật chính xác và trả lời có trích dẫn nguồn.