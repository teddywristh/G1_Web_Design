"use strict";

// State, labels and small helpers
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
  sessions: [],
  sessionCursor: null,
  view: "chat",
  category: "Tất cả",
  chats: [],
  chatId: null,
  saved: new Set(),
  selected: new Set(),
  documentId: null,
  authMode: "login",
};
const MAX_KBS = 5;
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
  upload_text_pdf: "Tải lên bản PDF có lớp chữ (chưa hỗ trợ OCR).",
  await_admin_review: "Quản trị viên cần xuất bản bản dựng mới.",
  upload_public_pdf: "Hãy tải lại tài liệu công khai và xác nhận tài liệu không có dữ liệu cá nhân hoặc thông tin mật.",
  check_storage: "Tải lên thất bại. Kiểm tra Firebase Storage rồi thử lại bằng tài liệu mới.",
  check_job: "Không tìm thấy job với cấu hình embedding hiện tại. Liên hệ quản trị viên để kiểm tra.",
  reindex: "Model embedding đã đổi. Mở tài liệu và chọn xử lý lại để lập chỉ mục local.",
  wait_rate_limit: "Đang giãn lượt embedding. Worker sẽ tự thử lại sau.",
};
const STAGE_TEXT = { upload: "tải PDF", parse: "đọc PDF", embed: "tạo embeddings", publish: "tạo chỉ mục" };
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
let pollTimer;
let googleTimer;
let blobUrl = null;

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
    kbs: [...state.selected],
    provider: $("#provider").value,
    model: $("#model").value,
    engine: $("#engine").value,
    credentialSource: $("#credential-source").value,
    retrievalMode: $("#retrieval-mode").value,
  });
  renderCounts();
}

function renderCounts() {
  $("#document-count").textContent = state.docs.length;
  $("#saved-count").textContent = state.docs.filter((doc) => state.saved.has(doc.id)).length;
  $("#chat-count").textContent = state.chats.length;
}

// Sign-in, registration and session
function showAuth(message = "") {
  state.user = null;
  $("#auth-view").hidden = false;
  $("#sidebar").hidden = true;
  $("#app-shell").hidden = true;
  $("#auth-error").textContent = message;
}

function showGuest(message = "") {
  state.user = null;
  state.kbs = []; state.kbId = null; state.docs = []; state.selected = new Set();
  state.chats = readStore("chats", []); state.chatId = null;
  state.saved = new Set(readStore("saved", []));
  $("#auth-view").hidden = true;
  $("#sidebar").hidden = false;
  $("#app-shell").hidden = false;
  $("#user-name").textContent = "Khách trải nghiệm";
  $("#user-role").textContent = "Đăng nhập để sử dụng AI";
  $("#account-action").textContent = "Đăng nhập";
  $("#register-action").hidden = false;
  $("#backend-label").textContent = "Chế độ trải nghiệm";
  renderScope(); renderKbSelect(); renderChat();
  navigate("chat");
  if (message) notify(message);
}

function setAuthMode(mode) {
  state.authMode = mode;
  const register = mode === "register";
  $("#auth-title").textContent = register ? "Tạo tài khoản" : "Đăng nhập Legal AI";
  $("#auth-submit").textContent = register ? "Đăng ký" : "Đăng nhập";
  $("#auth-switch").textContent = register
    ? "Đã có tài khoản? Đăng nhập"
    : "Chưa có tài khoản? Đăng ký";
  $("#name-field").hidden = !register;
  $("#name-field input").required = register;
  $("#confirm-field").hidden = !register;
  $("#confirm-field input").required = register;
  $("#auth-form [name=password]").minLength = register ? 8 : 1;
  $("#auth-form [name=password]").autocomplete = register ? "new-password" : "current-password";
}

async function enterSession(session) {
  setCsrf(session.csrfToken);
  state.user = session.user;
  state.chats = readStore("chats", []);
  state.saved = new Set(readStore("saved", []));
  const prefs = readStore("prefs", {});
  state.selected = new Set(prefs.kbs || []);
  $("#provider").value = prefs.provider || "openai";
  $("#model").value = prefs.model || "";
  $("#engine").value = prefs.engine || "direct";
  $("#credential-source").value = prefs.credentialSource || "auto";
  $("#retrieval-mode").value = prefs.retrievalMode || "hybrid";
  $("#as-of").value = "";
  $("#auth-view").hidden = true;
  $("#sidebar").hidden = false;
  $("#app-shell").hidden = false;
  $("#user-name").textContent = state.user.displayName;
  $("#user-role").textContent = isAdmin() ? "Quản trị viên" : "Người dùng";
  $("#account-action").textContent = "Tài khoản";
  $("#register-action").hidden = true;
  $("#backend-label").textContent = "Đã kết nối";
  $("#account-info").textContent = `${state.user.displayName} · ${state.user.email || ""}`;
  await loadKbs();
  await loadConnections({ restore: !prefs.credentialSource });
  renderChat();
  navigate("chat");
  if (window.google?.accounts?.id) setupGoogle();
}

async function boot() {
  setAuthMode("login");
  try {
    await enterSession(await api.get("/auth/me"));
  } catch (error) {
    showGuest(error.status === 0 ? error.message : "");
  }
  setupGoogle();
}

async function setupGoogle() {
  clearTimeout(googleTimer);
  let challenge;
  try { challenge = await api.get("/auth/google/challenge"); } catch { return; }
  const clientId = document.querySelector('meta[name="google-client-id"]').content || challenge.clientId;
  if (!clientId) return;
  const render = () => {
    try {
      const { nonce } = challenge;
      google.accounts.id.initialize({
        client_id: clientId,
        nonce,
        callback: async (response) => {
          try {
            await enterSession(await api.post("/auth/google", { credential: response.credential }));
          } catch (error) {
            if (state.user) notify(error.message);
            else $("#auth-error").textContent = error.message;
            setupGoogle();
          }
        },
      });
      $("#google-button").replaceChildren();
      $("#google-link-button").replaceChildren();
      google.accounts.id.renderButton($("#google-button"), { theme: "outline", size: "large" });
      google.accounts.id.renderButton($("#google-link-button"), { theme: "outline", size: "large" });
      googleTimer = setTimeout(setupGoogle, 240000);
    } catch {
      /* Google sign-in is optional; email sign-in still works. */
    }
  };
  if (window.google?.accounts?.id) render();
  else if (!document.querySelector('script[data-google-identity]')) {
    const script = element("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.dataset.googleIdentity = "true";
    script.onload = render;
    document.head.append(script);
  }
}

$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const register = state.authMode === "register";
  const body = { email: String(data.get("email")), password: String(data.get("password")) };
  if (register) body.displayName = String(data.get("displayName")).trim();
  if (new TextEncoder().encode(body.password).length > 72) {
    $("#auth-error").textContent = "Mật khẩu tối đa 72 byte UTF-8.";
    return;
  }
  if (register && body.password !== String(data.get("confirmation"))) {
    $("#auth-error").textContent = "Mật khẩu xác nhận không khớp.";
    return;
  }
  $("#auth-submit").disabled = true;
  try {
    const session = await api.post(register ? "/auth/register" : "/auth/login", body);
    form.reset();
    await enterSession(session);
  } catch (error) {
    $("#auth-error").textContent =
      error.status === 401 ? "Email hoặc mật khẩu không đúng." : error.message;
  } finally {
    $("#auth-submit").disabled = false;
  }
});
$("#auth-switch").addEventListener("click", () =>
  setAuthMode(state.authMode === "login" ? "register" : "login"),
);
$("#guest-back").addEventListener("click", () => showGuest());
$("#register-action").addEventListener("click", () => { setAuthMode("register"); showAuth(); });

async function logout(all) {
  try {
    await api.post(all ? "/auth/logout-all" : "/auth/logout", {});
  } catch {
    /* Even if the server call fails, drop local state. */
  }
  clearTimeout(pollTimer);
  // Chat history and cited text must not outlive the session on a shared computer.
  ["chats", "saved", "prefs"].forEach((name) => localStorage.removeItem(storeKey(name)));
  Object.assign(state, { kbs: [], docs: [], chats: [], chatId: null, saved: new Set() });
  Object.assign(state, { selected: new Set(), connections: [], kbId: null, aiOptions: null,
    chatgpt: { connected: false, pending: false }, sessions: [], sessionCursor: null });
  setCsrf("");
  $("#messages").replaceChildren();
  showGuest();
  setupGoogle();
}
$("#logout").addEventListener("click", () => logout(false));
$("#logout-all").addEventListener("click", () => logout(true));

// Navigation
function closeMenu() {
  $("#sidebar").classList.remove("is-open");
  $("#menu-overlay").hidden = true;
  $("#menu-toggle").setAttribute("aria-expanded", "false");
}

function navigate(view) {
  if (view === "settings" && !state.user) { setAuthMode("login"); showAuth("Đăng nhập để quản lý tài khoản và kết nối AI."); return; }
  state.view = view;
  document.querySelectorAll(".view").forEach((section) => {
    section.hidden = true;
  });
  $(`#${view === "saved" ? "library" : view}-view`).hidden = false;
  $("#page-label").textContent = {
    chat: "Hỏi đáp",
    library: "Thư viện tài liệu",
    saved: "Đã lưu",
    settings: "Thiết lập",
  }[view];
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
    if (button.dataset.view === view) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  if (view === "library" || view === "saved") {
    if (state.user) loadDocs(true);
    else { renderKbControls(); renderDocuments(); }
  }
  if (view === "settings") { loadConnections(); loadSessions(); }
  if (view === "chat" && state.user) loadKbs();
  closeMenu();
}

// Knowledge bases
async function loadKbs() {
  try {
    state.kbs = await api.get("/knowledge-bases");
  } catch (error) {
    notify(error.message);
    state.kbs = [];
  }
  const ids = state.kbs.map((kb) => kb.id);
  state.selected = new Set([...state.selected].filter((id) => ids.includes(id)));
  if (!state.kbs.some((kb) => kb.id === state.kbId)) state.kbId = state.kbs[0]?.id || null;
  renderScope();
  renderKbSelect();
}

function kbTitle(kb) {
  return kb.kind === "shared" ? "Kho luật dùng chung" : kb.title;
}

function renderScope() {
  const box = $("#kb-scope");
  box.replaceChildren(element("legend", "", `Nguồn tra cứu (tối đa ${MAX_KBS} kho)`));
  state.kbs.forEach((kb) => {
    const label = element("label", "scope-option");
    const input = element("input");
    input.type = "checkbox";
    input.value = kb.id;
    input.checked = state.selected.has(kb.id);
    input.addEventListener("change", () => {
      if (input.checked && state.selected.size >= MAX_KBS) {
        input.checked = false;
        notify(`Chỉ chọn tối đa ${MAX_KBS} kho cho mỗi câu hỏi.`);
        return;
      }
      if (input.checked) state.selected.add(kb.id);
      else state.selected.delete(kb.id);
      persist();
    });
    label.append(input, element("span", "", kbTitle(kb) + (kb.ready ? "" : " (chưa sẵn sàng)")));
    box.append(label);
  });
  if (!state.kbs.length) box.append(element("p", "small-print", "Chưa có kho nào."));
}

function renderKbSelect() {
  const select = $("#kb-select");
  select.replaceChildren();
  state.kbs.forEach((kb) => select.add(new Option(kbTitle(kb), kb.id)));
  select.value = state.kbId || "";
  renderKbControls();
}

function currentKb() {
  return state.kbs.find((kb) => kb.id === state.kbId);
}

function renderKbControls() {
  const kb = currentKb();
  const shared = kb?.kind === "shared";
  $("#new-kb").hidden = !state.user;
  $("#open-upload").hidden = !kb || (shared && !isAdmin());
  $("#category-tabs").hidden = !shared;
  $("#publish-kb").hidden = !(
    shared &&
    isAdmin() &&
    kb.latestGeneration &&
    kb.latestGeneration !== kb.activeIndexGeneration
  );
  $("#library-note").textContent = !state.user
    ? "Đăng nhập để xem và quản lý tài liệu."
    : shared ? "Văn bản do quản trị viên quản lý, dùng chung cho mọi người."
      : "Tài liệu riêng chỉ mình bạn thấy; dùng khi chọn kho này trong hỏi đáp.";
}

$("#kb-select").addEventListener("change", (event) => {
  state.kbId = event.target.value;
  renderKbControls();
  loadDocs(true);
});
$("#new-kb").addEventListener("click", async () => {
  const title = prompt("Tên kho riêng");
  if (!title?.trim()) return;
  try {
    const kb = await api.post("/knowledge-bases", { title: title.trim() });
    state.kbId = kb.id;
    await loadKbs();
    loadDocs(true);
  } catch (error) {
    notify(error.message);
  }
});
$("#publish-kb").addEventListener("click", async () => {
  const kb = currentKb();
  try {
    await api.post(`/admin/knowledge-bases/${kb.id}/publish`, { generationId: kb.latestGeneration }, {
      version: kb.version,
    });
    notify("Đã xuất bản bản dựng mới.");
    await loadKbs();
    renderKbControls();
  } catch (error) {
    notify(error.message);
  }
});

// Documents: shared (admin-managed) or private, one table for both
function normalizeDoc(raw, kb) {
  const shared = kb.kind === "shared";
  return {
    id: raw.id,
    kbId: kb.id,
    shared,
    title: shared ? raw.title : raw.displayTitle,
    number: shared ? raw.documentNumber : "Tài liệu riêng",
    category: shared ? raw.documentType : "Riêng",
    authority: shared ? raw.issuingAuthority : "Của bạn",
    date: raw.createdAt,
    version: raw.version,
    fileState: raw.fileState,
    processing: null,
  };
}

async function loadDocs(reset) {
  const kb = currentKb();
  if (!kb) return;
  if (reset) {
    state.docs = [];
    state.nextCursor = null;
    renderDocuments();
  }
  const params = new URLSearchParams({ limit: "20" });
  if (state.nextCursor) params.set("cursor", state.nextCursor);
  let path = `/knowledge-bases/${kb.id}/documents?${params}`;
  if (kb.kind === "shared") {
    if (state.category !== "Tất cả") params.set("documentType", state.category);
    path = `/documents?${params}`;
  }
  try {
    const page = await api.get(path);
    state.docs.push(...page.items.map((item) => normalizeDoc(item, kb)));
    state.nextCursor = page.nextCursor;
  } catch (error) {
    notify(error.message);
  }
  renderDocuments();
  if (kb.kind === "private") refreshProcessing();
}

async function refreshProcessing() {
  clearTimeout(pollTimer);
  const pending = state.docs.filter((doc) => !doc.shared);
  await Promise.all(
    pending.map(async (doc) => {
      try {
        doc.processing = await api.get(`/knowledge-bases/${doc.kbId}/documents/${doc.id}/processing`);
      } catch {
        doc.processing = { status: "status_unavailable" };
      }
    }),
  );
  if (state.view === "library" || state.view === "saved") renderDocuments();
  const busy = pending.some((doc) => ["queued", "processing", "status_unavailable"].includes(doc.processing?.status));
  if (busy && state.view !== "chat" && state.view !== "settings") {
    pollTimer = setTimeout(refreshProcessing, 4000);
  }
}

function coverageNote(doc) {
  const coverage = doc.processing?.embeddingCoverage;
  if (!coverage || coverage.indexed >= coverage.total) return "";
  const last = coverage.start + coverage.indexed - 1;
  return `Chỉ lập chỉ mục đoạn ${coverage.start}–${last} / ${coverage.total}; câu trả lời có thể thiếu thông tin ngoài phạm vi này.`;
}

function processingNote(doc) {
  if (doc.fileState === "upload_failed") return ACTION_TEXT.check_storage;
  if (doc.processing?.nextAction === "wait_rate_limit") {
    const next = doc.processing.nextRunAt && new Date(doc.processing.nextRunAt);
    return next && !Number.isNaN(next.valueOf())
      ? `Đang giãn lượt embedding. Sẽ thử lại sau ${next.toLocaleString("vi-VN")}.`
      : ACTION_TEXT.wait_rate_limit;
  }
  return coverageNote(doc) || ACTION_TEXT[doc.processing?.nextAction] || "";
}

function statusBadge(doc) {
  if (doc.shared) return element("span", "status-badge ready", "Đã có PDF");
  const status = doc.fileState === "upload_failed" ? "failed" : doc.processing?.status || "status_unavailable";
  const good = status === "ready";
  const bad = ["failed", "needs_ocr", "revoked"].includes(status);
  const label = PROCESSING_TEXT[status] || status;
  const stage = status === "processing" && STAGE_TEXT[doc.processing?.stage];
  return element(
    "span",
    `status-badge ${good ? "ready" : bad ? "problem" : "uploaded"}`,
    stage ? `${label} · ${stage}` : label,
  );
}

function renderDocuments() {
  $("#library-title").textContent =
    state.view === "saved" ? "Tài liệu đã lưu" : "Thư viện tài liệu";
  const query = $("#search").value.trim().toLocaleLowerCase("vi");
  const pool = state.docs.filter((doc) => state.view !== "saved" || state.saved.has(doc.id));
  const filtered = pool.filter((doc) =>
    `${doc.title} ${doc.number} ${doc.authority}`.toLocaleLowerCase("vi").includes(query),
  );
  filtered.sort((a, b) =>
    $("#sort").value === "name"
      ? a.title.localeCompare(b.title, "vi")
      : String(b.date).localeCompare(String(a.date)),
  );
  $("#document-rows").replaceChildren();
  filtered.forEach((doc) => {
    const row = element("tr");
    const titleCell = element("td");
    const title = element("button", "document-title");
    title.append(
      element("strong", "", doc.title),
      element("small", "", `${doc.number} · ${doc.authority}`),
    );
    title.addEventListener("click", () => openDocument(doc.id));
    titleCell.append(title);
    const statusCell = element("td");
    statusCell.append(statusBadge(doc));
    if (processingNote(doc)) {
      statusCell.append(element("small", "processing-detail", processingNote(doc)));
    }
    const actions = element("td");
    const saved = state.saved.has(doc.id);
    const bookmark = element("button", "text-button", saved ? "Bỏ lưu" : "Lưu");
    bookmark.setAttribute("aria-label", `${saved ? "Bỏ lưu" : "Lưu"} ${doc.title}`);
    bookmark.addEventListener("click", () => toggleSaved(doc.id));
    const open = element("button", "text-button", "Xem");
    open.setAttribute("aria-label", `Xem ${doc.title}`);
    open.addEventListener("click", () => openDocument(doc.id));
    actions.append(bookmark, open);
    row.append(
      titleCell,
      element("td", "", doc.category || ""),
      element("td", "date-cell", doc.date ? new Date(doc.date).toLocaleDateString("vi-VN") : ""),
      statusCell,
      actions,
    );
    $("#document-rows").append(row);
  });
  $("#empty-library").hidden = filtered.length > 0;
  $("#load-more").hidden = !state.nextCursor;
  $("#result-count").textContent = `Hiển thị ${filtered.length} / ${pool.length} tài liệu`;
  renderCounts();
}

function toggleSaved(id) {
  if (state.saved.has(id)) state.saved.delete(id);
  else state.saved.add(id);
  persist();
  renderDocuments();
  $("#detail-bookmark").textContent = state.saved.has(id) ? "Bỏ đánh dấu" : "Đánh dấu";
}

$("#search").addEventListener("input", renderDocuments);
$("#sort").addEventListener("change", renderDocuments);
$("#load-more").addEventListener("click", () => loadDocs(false));
$("#category-tabs").addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (!button) return;
  state.category = button.dataset.category;
  document.querySelectorAll("[data-category]").forEach((tab) => {
    const selected = tab === button;
    tab.classList.toggle("selected", selected);
    tab.setAttribute("aria-pressed", String(selected));
  });
  loadDocs(true);
});

// Reading, retrying and deleting
function downloadPath(doc) {
  return doc.shared
    ? `/documents/${doc.id}/download`
    : `/knowledge-bases/${doc.kbId}/documents/${doc.id}/download`;
}

async function openDocument(id) {
  const doc = state.docs.find((item) => item.id === id);
  if (!doc) return;
  state.documentId = id;
  $("#pdf-error").textContent = "";
  $("#detail-title").textContent = doc.title;
  $("#detail-meta").textContent = [doc.number, doc.authority, coverageNote(doc)].filter(Boolean).join(" · ");
  $("#detail-bookmark").textContent = state.saved.has(id) ? "Bỏ đánh dấu" : "Đánh dấu";
  $("#delete-document").hidden = doc.shared && !isAdmin();
  const status = doc.processing;
  $("#retry-document").hidden = !(status && (status.retryable || status.status === "needs_ocr"));
  $("#pdf-viewer").hidden = true;
  $("#pdf-empty").hidden = false;
  $("#pdf-empty-title").textContent = "Đang tải PDF…";
  $("#pdf-empty-note").textContent = status?.nextAction ? ACTION_TEXT[status.nextAction] || "" : "";
  if (!$("#document-dialog").open) $("#document-dialog").showModal();
  try {
    const blob = await api.blob(downloadPath(doc));
    if (state.documentId !== id) return;
    URL.revokeObjectURL(blobUrl);
    blobUrl = URL.createObjectURL(blob);
    $("#pdf-viewer").src = blobUrl;
    $("#pdf-viewer").hidden = false;
    $("#pdf-empty").hidden = true;
    $("#download-pdf").href = blobUrl;
    $("#download-pdf").download = `${doc.title}.pdf`;
    $("#download-pdf").hidden = false;
  } catch (error) {
    $("#pdf-empty-title").textContent = "Không mở được PDF";
    $("#pdf-error").textContent = error.message;
    $("#download-pdf").hidden = true;
  }
}

$("#retry-document").addEventListener("click", async () => {
  const doc = state.docs.find((item) => item.id === state.documentId);
  try {
    await api.post(`/knowledge-bases/${doc.kbId}/documents/${doc.id}/reprocess`, undefined, {
      version: doc.version,
    });
    $("#document-dialog").close();
    notify("Đã đưa tài liệu vào hàng đợi xử lý lại.");
    refreshProcessing();
  } catch (error) {
    $("#pdf-error").textContent = error.message;
  }
});
$("#detail-bookmark").addEventListener("click", () => toggleSaved(state.documentId));
$("#delete-document").addEventListener("click", async () => {
  const doc = state.docs.find((item) => item.id === state.documentId);
  if (!doc || !confirm(`Xóa "${doc.title}"? Tài liệu sẽ ngừng được dùng để trả lời ngay.`)) return;
  try {
    await api.del(
      doc.shared ? `/admin/documents/${doc.id}` : `/knowledge-bases/${doc.kbId}/documents/${doc.id}`,
      doc.version,
    );
    state.docs = state.docs.filter((item) => item.id !== doc.id);
    state.saved.delete(doc.id);
    $("#document-dialog").close();
    persist();
    renderDocuments();
    notify("Đã xóa tài liệu.");
  } catch (error) {
    $("#pdf-error").textContent = error.message;
  }
});
$("#document-dialog").addEventListener("close", () => {
  $("#pdf-viewer").removeAttribute("src");
  URL.revokeObjectURL(blobUrl);
  blobUrl = null;
  state.documentId = null;
});

// Upload: private KBs take a title; the shared KB (admin) takes full legal metadata
async function validatePdf(file) {
  if (!file) return "Hãy chọn file PDF.";
  if (!file.name.toLowerCase().endsWith(".pdf") || (file.type && file.type !== "application/pdf"))
    return "Vui lòng chọn đúng file PDF.";
  if (file.size > 20 * 1024 * 1024) return "PDF vượt quá giới hạn 20 MB.";
  if ((await file.slice(0, 5).text()) !== "%PDF-") return "File không có định dạng PDF hợp lệ.";
  return null;
}

let uploadFile = null;
function selectUploadFile(file) {
  uploadFile = file || null;
  $("#file-label").textContent = file
    ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`
    : "Chọn hoặc kéo thả PDF vào đây";
  $("#upload-error").textContent = "";
}

$("#open-upload").addEventListener("click", () => {
  const shared = currentKb().kind === "shared";
  $("#upload-form").reset();
  $("#upload-progress").textContent = "";
  selectUploadFile(null);
  $("#shared-fields").hidden = !shared;
  $("#upload-public-label").hidden = !state.aiOptions?.embedding?.requiresPublicInput;
  $("#upload-public-confirm").required = Boolean(state.aiOptions?.embedding?.requiresPublicInput);
  $("#upload-notice").textContent = shared
    ? "Văn bản dùng chung. Sau khi xử lý xong, hãy xuất bản bản dựng mới để mọi người tra cứu được."
    : "Chỉ bạn xem được tài liệu này. Hệ thống đọc nền; khi trạng thái là Sẵn sàng tra cứu, hãy chọn kho này trong Hỏi đáp.";
  $("#upload-dialog").showModal();
});
$("#pdf-file").addEventListener("change", (event) => selectUploadFile(event.target.files[0]));
$("#drop-zone").addEventListener("dragover", (event) => event.preventDefault());
$("#drop-zone").addEventListener("drop", (event) => {
  event.preventDefault();
  selectUploadFile(event.dataTransfer.files[0]);
});

$("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const kb = currentKb();
  const data = new FormData(event.currentTarget);
  const title = String(data.get("title")).trim();
  $("#save-document").disabled = true;
  $("#upload-progress").textContent = "Đang kiểm tra và tải PDF lên…";
  try {
    const error = await validatePdf(uploadFile);
    if (error || !title) {
      $("#upload-error").textContent = error || "Vui lòng nhập tên tài liệu.";
      $("#upload-progress").textContent = "";
      return;
    }
    if (state.aiOptions?.embedding?.requiresPublicInput && !$("#upload-public-confirm").checked) {
      $("#upload-error").textContent = "Xác nhận tài liệu không chứa dữ liệu cá nhân hoặc thông tin mật trước khi xử lý.";
      $("#upload-progress").textContent = "";
      return;
    }
    let created;
    let filePath;
    if (kb.kind === "shared") {
      const body = {
        title,
        documentNumber: String(data.get("number")).trim(),
        documentType: String(data.get("category")),
        issuingAuthority: String(data.get("authority")).trim(),
        issueDate: String(data.get("issueDate")),
        status: String(data.get("status")),
      };
      if (!body.documentNumber || !body.issuingAuthority || !body.issueDate) {
        $("#upload-error").textContent = "Cần số hiệu, cơ quan ban hành và ngày ban hành.";
        $("#upload-progress").textContent = "";
        return;
      }
      if (data.get("effectiveDate")) body.effectiveDate = String(data.get("effectiveDate"));
      created = await api.post("/admin/documents", body);
      filePath = `/admin/documents/${created.id}/file`;
    } else {
      created = await api.post(`/knowledge-bases/${kb.id}/documents`, { displayTitle: title });
      filePath = `/knowledge-bases/${kb.id}/documents/${created.id}/file`;
    }
    if (state.aiOptions?.embedding?.requiresPublicInput && $("#upload-public-confirm").checked)
      filePath += "?public_embedding_input_confirmed=true";
    await api.upload(filePath, uploadFile, created.version);
    $("#upload-dialog").close();
    notify("Đã tải lên. Tài liệu đang được xử lý nền.");
    await loadKbs();
    loadDocs(true);
  } catch (error) {
    $("#upload-error").textContent = error.message;
    $("#upload-progress").textContent = "Chưa hoàn tất tải lên. Hãy kiểm tra thông báo lỗi.";
    loadDocs(true);
  } finally {
    $("#save-document").disabled = false;
  }
});

// Chat
function activeChat() {
  return state.chats.find((chat) => chat.id === state.chatId);
}

function newChat() {
  state.chatId = null;
  $("#query-public-confirm").checked = false;
  $("#question-form").reset();
  renderChat();
  navigate("chat");
  $("#question").focus();
}

// Turn "[1]" markers in an answer into buttons that open the cited evidence.
function answerNode(data) {
  const box = element("div", "answer-text");
  (data.answer || "").split("\n").forEach((line) => {
    const paragraph = element("p");
    line.split(/(\[\d+\])/).forEach((part) => {
      const match = part.match(/^\[(\d+)\]$/);
      const citation = match && data.citations?.[Number(match[1]) - 1];
      if (!citation) {
        paragraph.append(part);
        return;
      }
      const button = element("button", "cite", part);
      button.addEventListener("click", () => openEvidence(citation));
      paragraph.append(button);
    });
    box.append(paragraph);
  });
  return box;
}

function listBlock(title, items) {
  const block = element("div", "answer-block");
  block.append(element("strong", "", title));
  const list = element("ul");
  items.forEach((item) => list.append(element("li", "", item)));
  block.append(list);
  return block;
}

function assistantBubble(message) {
  const bubble = element("div", "answer-message");
  bubble.append(element("span", "", "Legal AI"));
  const data = message.data;
  if (!data) {
    bubble.append(element("p", "", message.text));
    return bubble;
  }
  const head = element("div", "answer-head");
  head.append(
    element("span", `status-badge ${data.status === "answered" ? "ready" : "uploaded"}`, STATUS_TEXT[data.status] || data.status),
  );
  if (data.as_of) head.append(element("small", "", `Mốc thời gian: ${new Date(data.as_of).toLocaleDateString("vi-VN")}`));
  if (data.provider) {
    const source = { chatgpt: "ChatGPT cá nhân", personal: "Key cá nhân", shared: "Key dùng chung" }[data.credential_source] || data.credential_source || "";
    head.append(element("small", "", `${data.provider} · ${source}`));
  }
  bubble.append(head, answerNode(data));
  if (data.missing_facts?.length) bubble.append(listBlock("Cần bổ sung", data.missing_facts));
  if (data.assumptions?.length) bubble.append(listBlock("Giả định", data.assumptions));
  if (data.citations?.length) {
    const block = element("div", "answer-block");
    block.append(element("strong", "", "Nguồn"));
    data.citations.forEach((citation, index) => {
      const button = element("button", "citation-row");
      const place = [citation.article, citation.clause].filter(Boolean).join(" · ");
      button.append(
        element("span", "", `[${index + 1}] ${citation.document_title}${place ? " · " + place : ""}`),
        element("small", "", SOURCE_TEXT[citation.source_type] || ""),
      );
      button.addEventListener("click", () => openEvidence(citation));
      block.append(button);
    });
    bubble.append(block);
  }
  if (data.source_limitations?.length) {
    const notes = element("div", "limit-chips");
    data.source_limitations.forEach((code) => notes.append(element("span", "", limitText(code))));
    bubble.append(notes);
  }
  return bubble;
}

function renderChat() {
  const active = activeChat();
  const hasMessages = Boolean(active?.messages.length);
  $("#history-bar").hidden = state.chats.length === 0;
  $("#history-select").replaceChildren(new Option("Chọn cuộc trò chuyện", ""));
  state.chats.forEach((chat) =>
    $("#history-select").add(new Option(chat.title || "Chưa đặt tên", chat.id)),
  );
  $("#history-select").value = active?.id || "";
  $("#delete-chat").hidden = !active;
  $("#welcome").hidden = hasMessages;
  $("#suggestions").hidden = hasMessages;
  $("#conversation").hidden = !hasMessages;
  $("#chat-title").value = active?.title || "";
  $("#messages").replaceChildren();
  active?.messages.forEach((message) => {
    if (message.role === "assistant") {
      $("#messages").append(assistantBubble(message));
      return;
    }
    const bubble = element("div", "question-message");
    bubble.append(element("span", "", "Bạn"), element("p", "", message.text));
    $("#messages").append(bubble);
  });
  $("#messages").scrollTop = $("#messages").scrollHeight;
  $("#send-question").disabled = !$("#question").value.trim();
  renderCounts();
}

function requestBody(question) {
  const provider = $("#provider").value;
  const body = {
    question,
    provider,
    credential_source: $("#credential-source").value,
    engine: $("#engine").value,
    knowledge_base_ids: [...state.selected],
    retrieval_mode: $("#retrieval-mode").value,
    web_mode: $("#web-search").checked ? "official" : "off",
    public_embedding_input_confirmed: $("#query-public-confirm").checked,
  };
  if ($("#as-of").value) body.as_of = $("#as-of").value;
  if ($("#model").value.trim()) body.model = $("#model").value.trim();
  return body;
}

$("#question-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = $("#question").value.trim();
  if (!question) return;
  if (!state.user) { setAuthMode("login"); showAuth("Đăng nhập để đặt câu hỏi và kết nối AI."); return; }
  const hasReadyKb = state.kbs.some((kb) => kb.ready && state.selected.has(kb.id));
  if (hasReadyKb && state.aiOptions?.embedding?.requiresPublicInput && $("#retrieval-mode").value === "hybrid" && !$("#query-public-confirm").checked) {
    notify("Xác nhận câu hỏi không chứa dữ liệu cá nhân hoặc thông tin mật.");
    return;
  }
  if (["anthropic", "deepseek", "openrouter"].includes($("#provider").value) && !$("#model").value.trim()) {
    notify("Nhập ID model của nhà cung cấp đã chọn.");
    return;
  }
  let active = activeChat();
  if (!active) {
    active = { id: crypto.randomUUID(), title: question.slice(0, 70), date: new Date().toISOString(), messages: [] };
    state.chats.unshift(active);
    state.chatId = active.id;
  }
  active.messages.push({ role: "user", text: question });
  $("#question-form").reset();
  $("#send-question").disabled = true;
  persist();
  renderChat();
  const chatId = active.id;
  $("#assistant-status").textContent = "Đang tra cứu nguồn và soạn câu trả lời…";
  let reply;
  try {
    const body = requestBody(question);
    $("#query-public-confirm").checked = false;
    const data = await api.post("/rag/ask", body);
    reply = { role: "assistant", text: data.answer, data: slimResponse(data) };
  } catch (error) {
    if (error.code === "chatgpt_disconnected") {
      state.chatgpt = { ...state.chatgpt, connected: false, pending: false };
      renderChatgpt();
    }
    reply = { role: "assistant", text: error.message };
  }
  $("#assistant-status").textContent =
    "Lịch sử hội thoại chỉ lưu trên thiết bị này và bị xóa khi đăng xuất. Câu trả lời không thay thế tư vấn pháp lý.";
  const chat = state.chats.find((item) => item.id === chatId);
  if (!chat) return;
  chat.messages.push(reply);
  persist();
  if (state.chatId === chatId) renderChat();
});

// Keep only what the view needs; retrieved_chunks stay out of the history.
function slimResponse(data) {
  return {
    status: data.status,
    answer: data.answer,
    as_of: data.as_of,
    citations: data.citations,
    assumptions: data.assumptions,
    missing_facts: data.missing_facts,
    source_limitations: data.source_limitations,
    provider: data.provider,
    credential_source: data.credential_source,
  };
}

$("#question").addEventListener("input", () => {
  $("#query-public-confirm").checked = false;
  $("#send-question").disabled = !$("#question").value.trim();
});
$("#question").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    $("#question-form").requestSubmit();
  }
});
$("#suggestions").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  $("#query-public-confirm").checked = false;
  $("#question").value = button.textContent;
  $("#send-question").disabled = false;
  $("#question").focus();
});
$("#history-select").addEventListener("change", (event) => {
  state.chatId = event.target.value || null;
  $("#question-form").reset();
  renderChat();
});
$("#chat-title").addEventListener("input", (event) => {
  const active = activeChat();
  if (!active) return;
  active.title = event.target.value;
  persist();
  $("#history-select").selectedOptions[0].textContent = active.title || "Chưa đặt tên";
});
$("#delete-chat").addEventListener("click", () => {
  state.chats = state.chats.filter((chat) => chat.id !== state.chatId);
  persist();
  newChat();
});
$("#provider").addEventListener("change", () => {
  const provider = $("#provider").value;
  $("#model").value = "";
  if (["deepseek", "openrouter"].includes(provider)) {
    $("#engine").value = "opencode";
    $("#retrieval-mode").value = "keyword";
  }
  if (provider === "anthropic") $("#engine").value = "direct";
  if (provider !== "openai" && $("#credential-source").value === "chatgpt") $("#credential-source").value = "auto";
  syncAiControls(); persist();
});
$("#engine").addEventListener("change", () => {
  if ($("#engine").value === "direct" && $("#credential-source").value === "chatgpt") $("#credential-source").value = "auto";
  if ($("#engine").value === "opencode") $("#retrieval-mode").value = "keyword";
  syncAiControls(); persist();
});
$("#credential-source").addEventListener("change", () => {
  if ($("#credential-source").value === "chatgpt") $("#retrieval-mode").value = "keyword";
  syncAiControls(); renderChatgpt(); persist();
});
$("#retrieval-mode").addEventListener("change", () => { syncAiControls(); persist(); });
$("#model").addEventListener("change", persist);

// Evidence viewer: the server re-checks permission, deletion and publication each time.
async function openEvidence(citation) {
  $("#evidence-error").textContent = "";
  $("#evidence-limits").textContent = "";
  $("#evidence-link").hidden = true;
  $("#evidence-title").textContent = citation.document_title;
  $("#evidence-meta").textContent = "";
  $("#evidence-text").textContent = "";
  $("#evidence-dialog").showModal();
  if (!citation.provision_version_id) {
    $("#evidence-text").textContent = citation.quote || "";
    $("#evidence-meta").textContent = "Nguồn web, chưa xác minh hiệu lực";
    if (/^https:\/\//.test(citation.source_url || "")) {
      $("#evidence-link").href = citation.source_url;
      $("#evidence-link").hidden = false;
    }
    return;
  }
  try {
    const item = await api.get(`/evidence/${citation.provision_version_id}`);
    const place = [item.chapter && `Chương ${item.chapter}`, item.article, item.clause].filter(Boolean);
    const pages = item.pageStart === item.pageEnd ? `trang ${item.pageStart}` : `trang ${item.pageStart}–${item.pageEnd}`;
    $("#evidence-title").textContent = `${item.documentTitle}${item.documentNumber ? " · " + item.documentNumber : ""}`;
    $("#evidence-meta").textContent = `${place.join(" · ")} · ${pages} của PDF`;
    $("#evidence-text").textContent = item.text;
    $("#evidence-limits").textContent = item.limitations.map(limitText).join(" · ");
  } catch (error) {
    $("#evidence-error").textContent =
      error.status === 404 ? "Nguồn này không còn truy cập được (đã xóa hoặc thu hồi)." : error.message;
  }
}

// AI connections
function syncAiControls() {
  const provider = $("#provider").value;
  const engine = $("#engine").value;
  const source = $("#credential-source").value;
  const available = Boolean(state.aiOptions?.engines?.opencode);
  $("#engine option[value=opencode]").disabled = !available || provider === "anthropic";
  $("#engine option[value=direct]").disabled = ["deepseek", "openrouter"].includes(provider);
  const chatgptOption = $("#credential-source option[value=chatgpt]");
  chatgptOption.hidden = provider !== "openai" || engine !== "opencode" || !state.chatgpt.available;
  chatgptOption.disabled = !state.chatgpt.connected;
  $("#retrieval-mode option[value=hybrid]").disabled = source === "chatgpt" && !["openrouter", "local"].includes(state.aiOptions?.embedding?.provider);
  $("#query-public-label").hidden = !(state.aiOptions?.embedding?.requiresPublicInput && $("#retrieval-mode").value === "hybrid");
  $("#model").placeholder = provider === "openai" ? "Để trống dùng mặc định" : "Nhập ID model";
}

function selectChatgpt() {
  $("#provider").value = "openai";
  $("#engine").value = "opencode";
  $("#credential-source").value = "chatgpt";
  $("#retrieval-mode").value = "keyword";
  $("#model").value = "gpt-5.6-luna";
  syncAiControls();
  persist();
  renderChatgpt();
}

function renderChatgpt() {
  const connection = state.chatgpt;
  $("#chatgpt-status").textContent = !connection.available
    ? "Chưa bật trong môi trường này; OAuth OpenCode hiện chỉ hỗ trợ local."
    : connection.connected ? "Đã kết nối cho phiên local." : connection.pending
      ? (connection.url ? "Đang chờ đăng nhập ChatGPT." : "Phiên đăng nhập đang chờ. Hãy ngắt kết nối và bắt đầu lại để nhận mã mới.")
      : "Chưa kết nối.";
  $("#chatgpt-instructions").hidden = !connection.instructions;
  $("#chatgpt-instructions").textContent = connection.instructions || "";
  $("#chatgpt-link").hidden = !connection.url;
  if (connection.url) $("#chatgpt-link").href = connection.url;
  else $("#chatgpt-link").removeAttribute("href");
  $("#chatgpt-start").hidden = !connection.available || connection.connected || connection.pending;
  $("#chatgpt-finish").hidden = !connection.pending || !connection.url;
  $("#chatgpt-use").hidden = !connection.connected || $("#credential-source").value === "chatgpt";
  $("#chatgpt-disconnect").hidden = !connection.connected && !connection.pending;
  syncAiControls();
}

async function loadConnections({ restore = false } = {}) {
  if (!state.user) return;
  const userId = state.user.id;
  try {
    const options = await api.get("/ai/connections");
    if (state.user?.id !== userId) return;
    state.aiOptions = options;
    state.connections = options.connections;
    const available = Boolean(options.methods?.find((item) => item.id === "chatgpt_oauth")?.available);
    if (available) {
      const status = await api.get("/ai/chatgpt");
      if (state.user?.id !== userId) return;
      state.chatgpt = { ...state.chatgpt, ...status, available };
      if (restore && status.connected) selectChatgpt();
    } else {
      state.chatgpt = { available: false, connected: false, pending: false };
    }
  } catch (error) {
    notify(error.message);
    return;
  }
  const list = $("#connection-list");
  list.replaceChildren();
  renderChatgpt();
  const embedding = state.aiOptions?.embedding;
  $("#embedding-info").textContent = embedding?.provider === "local"
    ? `Embedding chạy trên GPU local (${embedding.model}); không cần khóa OpenRouter.`
    : embedding?.provider === "openrouter"
    ? `Embedding dùng OpenRouter (${embedding.model || "chưa chọn model"}) với key chung do hệ thống cấu hình${embedding.configured ? "." : "; chưa cấu hình đầy đủ."}`
    : "Embedding dùng khóa OpenAI; nếu không có khóa OpenAI, hãy dùng mục tìm theo số hiệu/điều.";
  $("#connection-scope option[value=shared]").hidden = !isAdmin();
  const names = { openai: "OpenAI", anthropic: "Claude", deepseek: "DeepSeek", openrouter: "OpenRouter" };
  state.connections
    .filter((item) => names[item.provider])
    .forEach((item) => {
      const row = element("li");
      const scope = item.scope === "personal" ? "cá nhân" : "dùng chung";
      row.append(element("span", "", `${names[item.provider]} · ${scope}: `));
      row.append(element("strong", "", item.configured ? (item.enabled ? "đã cấu hình" : "đang tắt") : "chưa có"));
      if ((item.scope === "personal" || isAdmin()) && item.origin === "stored" && item.configured) {
        const remove = element("button", "text-button danger", "Xóa");
        remove.addEventListener("click", async () => {
          try {
            const prefix = item.scope === "shared" ? "/admin" : "";
            await api.del(`${prefix}/ai/connections/${item.provider}`, item.version);
            loadConnections();
          } catch (error) {
            notify(error.message);
          }
        });
        row.append(remove);
      }
      list.append(row);
    });
}

$("#connection-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const provider = $("#connection-provider").value;
  const scope = $("#connection-scope").value;
  const current = state.connections.find((item) => item.provider === provider && item.scope === scope);
  try {
    await api.put(`${scope === "shared" ? "/admin" : ""}/ai/connections/${provider}`, {
      apiKey: $("#connection-key").value.trim(),
      expectedVersion: current?.version || 0,
      enabled: true,
    });
    notify("Đã lưu khóa. Khóa không được hiển thị lại.");
    loadConnections();
  } catch (error) {
    notify(error.message);
  } finally {
    $("#connection-key").value = "";
  }
});
$("#connection-scope").addEventListener("change", () => {
  $("#connection-key").placeholder = $("#connection-scope").value === "shared" ? "Khóa API dùng chung" : "Khóa API cá nhân";
});

async function chatgptAction(action) {
  const userId = state.user?.id;
  const buttons = ["#chatgpt-start", "#chatgpt-finish", "#chatgpt-use", "#chatgpt-disconnect"];
  buttons.forEach((selector) => { $(selector).disabled = true; });
  try {
    const result = action === "disconnect" ? await api.del("/ai/chatgpt") : await api.post(`/ai/chatgpt/${action}`, {});
    if (state.user?.id !== userId) return;
    if (action === "start") {
      const url = new URL(result.url);
      if (url.protocol !== "https:" || url.hostname !== "auth.openai.com" || url.username || url.password) throw new Error("Địa chỉ đăng nhập OpenAI không hợp lệ.");
      state.chatgpt = { available: true, pending: true, connected: false, url: url.href, instructions: result.instructions };
    } else if (action === "finish") {
      state.chatgpt = { available: true, pending: false, connected: Boolean(result.connected) };
      if (result.connected) { selectChatgpt(); notify("Đã kết nối ChatGPT cho phiên local."); }
    } else {
      state.chatgpt = { available: true, pending: false, connected: false };
      if ($("#credential-source").value === "chatgpt") { $("#credential-source").value = "auto"; persist(); }
    }
    renderChatgpt();
  } catch (error) { notify(error.message); }
  finally { buttons.forEach((selector) => { $(selector).disabled = false; }); }
}
$("#chatgpt-start").addEventListener("click", () => chatgptAction("start"));
$("#chatgpt-finish").addEventListener("click", () => chatgptAction("finish"));
$("#chatgpt-use").addEventListener("click", selectChatgpt);
$("#chatgpt-disconnect").addEventListener("click", () => chatgptAction("disconnect"));

async function loadSessions(cursor) {
  if (!state.user) return;
  const userId = state.user.id;
  try {
    const page = await api.get(`/auth/sessions${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`);
    if (state.user?.id !== userId) return;
    state.sessions = cursor ? [...state.sessions, ...page.items] : page.items;
    state.sessionCursor = page.nextCursor;
    $("#session-error").textContent = "";
    const list = $("#session-list"); list.replaceChildren();
    state.sessions.forEach((session) => {
      const row = element("li");
      const title = session.current ? "Thiết bị này" : "Phiên khác";
      const expires = session.active ? `Hết hạn ${new Date(session.expiresAt).toLocaleString("vi-VN")}` : "Đã hết hạn hoặc thu hồi";
      row.append(element("span", "", `${title} · ${expires}`));
      if (!session.current && session.active) {
        const button = element("button", "text-button danger", "Thu hồi");
        button.addEventListener("click", async () => {
          button.disabled = true;
          try { await api.del(`/auth/sessions/${encodeURIComponent(session.id)}`); await loadSessions(); }
          catch (error) { $("#session-error").textContent = error.message; button.disabled = false; }
        });
        row.append(button);
      }
      list.append(row);
    });
    $("#sessions-more").hidden = !state.sessionCursor;
  } catch (error) { $("#session-error").textContent = error.message; }
}
$("#sessions-more").addEventListener("click", () => loadSessions(state.sessionCursor));
document.querySelectorAll("[data-settings-target]").forEach((button) => button.addEventListener("click", () => {
  navigate("settings");
  const target = document.getElementById(button.dataset.settingsTarget);
  target.scrollIntoView({ behavior: "smooth", block: "start" });
  target.focus({ preventScroll: true });
}));

// Shared wiring
document
  .querySelectorAll("[data-view]")
  .forEach((button) => button.addEventListener("click", () => navigate(button.dataset.view)));
document
  .querySelectorAll('[data-action="new-chat"]')
  .forEach((button) => button.addEventListener("click", newChat));
document
  .querySelectorAll("[data-close]")
  .forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
$("#menu-toggle").addEventListener("click", () => {
  const isOpen = $("#sidebar").classList.toggle("is-open");
  $("#menu-overlay").hidden = !isOpen;
  $("#menu-toggle").setAttribute("aria-expanded", String(isOpen));
});
$("#menu-overlay").addEventListener("click", closeMenu);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeMenu();
});
$("#reset-data").addEventListener("click", () => {
  state.chats = [];
  state.chatId = null;
  state.saved = new Set();
  persist();
  renderChat();
  notify("Đã xóa lịch sử hội thoại và đánh dấu trên thiết bị.");
});

boot();
