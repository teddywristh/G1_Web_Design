// Trạng thái, nhãn hiển thị và hàm dùng chung
const $ = (selector) => document.querySelector(selector);
const state = {
  user: null,
  kbs: [],
  kbId: null,
  docs: [],
  nextCursor: null,
  connections: [],
  aiOptions: null,
  chatgpt: { connected: false, pending: false },
  models: { groups: [], apiKeysAvailable: true, loading: false },
  ai: null,
  sessions: [],
  sessionCursor: null,
  view: "chat",
  category: "Tất cả",
  chats: [],
  chatId: null,
  saved: new Set(),
  documentId: null,
  authMode: "login",
  pollTimer: null,
  pendingChat: null,
  chatError: null,
  settingsPage: "account",
};
const PROCESSING_TEXT = {
  queued: "Đang chờ xử lý",
  processing: "Đang xử lý",
  ready: "Sẵn sàng tra cứu",
  needs_ocr: "Cần OCR (PDF scan)",
  needs_review: "Chờ quản trị viên duyệt",
  failed: "Xử lý lỗi",
  revoked: "Đã thu hồi",
  upload: "Đang chờ tệp",
  status_unavailable: "Không kiểm tra được trạng thái",
};
const ACTION_TEXT = {
  configure_ai_key: "Thêm khóa OpenAI trong Thiết lập rồi chọn Xử lý lại.",
  upload_text_pdf: "Không thể đọc chữ trong PDF. Kiểm tra OCR tiếng Việt rồi chọn Xử lý lại.",
  await_admin_review: "Quản trị viên cần xuất bản bản dựng mới.",
  upload_public_pdf:
    "Hãy tải lại tài liệu công khai và xác nhận tài liệu không có dữ liệu cá nhân hoặc thông tin mật.",
  check_storage:
    "Lần tải trước không lưu được PDF. Hãy xóa mục này và tải lại tệp PDF gốc như một tài liệu mới.",
  check_job:
    "Không tìm thấy job với cấu hình embedding hiện tại. Liên hệ quản trị viên để kiểm tra.",
  reindex: "Model embedding đã đổi. Mở tài liệu và chọn xử lý lại để lập chỉ mục local.",
  wait_rate_limit: "Đang giãn lượt embedding. Worker sẽ tự thử lại sau.",
};
const STAGE_TEXT = {
  upload: "tải PDF",
  parse: "đọc PDF",
  embed: "tạo embeddings",
  publish: "tạo chỉ mục",
};
const STATUS_TEXT = {
  answered: "Có căn cứ",
  needs_clarification: "Cần bổ sung thông tin",
  insufficient_evidence: "Chưa đủ căn cứ",
  conflicting_sources: "Nguồn mâu thuẫn",
  temporarily_unavailable: "Tra cứu tạm gián đoạn",
};
const SOURCE_TEXT = {
  official_legal_text: "Văn bản pháp luật",
  official_guidance: "Hướng dẫn chính thức",
  user_document: "Tài liệu của bạn",
  commentary: "Bài viết tham khảo",
  court_decision: "Bản án",
};
const LIMIT_TEXT = {
  validity_unverified: "Hiệu lực chưa được xác minh",
  validity_conflict: "Hiệu lực đang có mâu thuẫn",
  expired_end_date_unknown: "Văn bản hết hiệu lực, chưa rõ ngày",
  partially_expired: "Hết hiệu lực một phần",
  user_document_unverified: "Tài liệu người dùng, chưa xác minh nguồn",
  web_validity_unverified: "Nguồn web, chưa xác minh hiệu lực",
  no_published_corpus: "Kho luật dùng chung chưa được xuất bản",
  no_lexical_index: "Chưa có chỉ mục từ khóa; chỉ tra theo số hiệu/điều",
  retrieval_budget_reached: "Đã chạm giới hạn số lượt tìm",
  output_validation_failed: "Câu trả lời không qua bước kiểm chứng nguồn",
  web_unavailable_for_provider: "Tra cứu web không khả dụng với nhà cung cấp này",
  web_search_unavailable: "Tra cứu web đang lỗi",
  web_no_results: "Không tìm thấy nguồn web phù hợp",
  web_source_unreadable: "Có nguồn web không đọc được",
  web_search_disabled: "Tìm web chưa được bật trên máy chủ",
  embedding_unavailable: "Tìm kiếm ngữ nghĩa tạm gián đoạn; đã thử nguồn khác",
  document_processing: "Trích từ PDF đã đọc; embedding vẫn đang xử lý",
  document_search_unavailable: "Tìm trong tài liệu đang gián đoạn",
  knowledge_base_not_ready: "Kho chưa sẵn sàng",
};
let toastTimer;

function notify(message) {
  clearTimeout(toastTimer);
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  toastTimer = setTimeout(() => {
    $("#toast").hidden = true;
  }, 4500);
}

// Use textContent for every server or user string; never inject HTML.
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function isAdmin() {
  return state.user?.role === "admin";
}

function limitText(code) {
  const [name, extra] = code.split(":");
  return LIMIT_TEXT[name] ? LIMIT_TEXT[name] + (extra ? ` (${extra.slice(0, 8)})` : "") : code;
}

// Per-account convenience data in localStorage (chat history, bookmarks, preferences).
function storeKey(name) {
  return `legal-ai.${name}.${state.user?.id || "guest"}`;
}

function readStore(name, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(storeKey(name)));
    return value ?? fallback;
  } catch {
    return fallback;
  }
}

function writeStore(name, value) {
  try {
    localStorage.setItem(storeKey(name), JSON.stringify(value));
  } catch {
    notify("Không thể lưu vào trình duyệt. Hãy kiểm tra dung lượng lưu trữ.");
  }
}

function persist() {
  writeStore("chats", state.chats);
  writeStore("saved", [...state.saved]);
  writeStore("prefs", {
    ai: state.ai,
  });
  renderCounts();
}

function renderCounts() {
  $("#document-count").textContent = state.docs.length;
  $("#chat-count").textContent = state.chats.length;
}

export {
  $,
  ACTION_TEXT,
  PROCESSING_TEXT,
  SOURCE_TEXT,
  STAGE_TEXT,
  STATUS_TEXT,
  element,
  isAdmin,
  limitText,
  notify,
  persist,
  readStore,
  renderCounts,
  state,
  storeKey,
};
