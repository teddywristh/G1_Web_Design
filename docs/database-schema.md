# Firebase data schema

The MVP uses Firebase Authentication, Cloud Firestore and Firebase Storage.
FastAPI is the only component allowed to access private Firestore and Storage
data. Admin SDK bypasses rules, so authorization remains server-side.

- `users/{uid}`: email, displayName, role (`user`/`admin`), createdAt, isActive.
- `legal_documents/{documentId}`: title, document number/type, authority, dates,
  status, storagePath, processingStatus, chunkCount and timestamps.
- `conversations/{conversationId}`: userId, title, timestamps and status.
- `conversations/{conversationId}/messages/{messageId}`: role, content, citations,
  timestamp and feedback.
- `system_logs/{logId}`: event, actor ID, status and timestamp.

Use Firestore server timestamps. List endpoints must use a limit and cursor.
