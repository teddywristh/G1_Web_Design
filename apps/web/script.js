"use strict";

// Dữ liệu mẫu và trạng thái giao diện
const DOCUMENT_KEY = "le-luat.documents.v1";
const CHAT_KEY = "le-luat.conversations.v1";
const sampleDocuments = [
  {
    id: "sample-1",
    title: "Bộ luật Lao động",
    number: "45/2019/QH14",
    category: "Bộ luật",
    authority: "Quốc hội",
    date: "2026-10-29",
    status: "ready",
    saved: true,
    sample: true,
  },
  {
    id: "sample-2",
    title: "Luật Doanh nghiệp",
    number: "59/2020/QH14",
    category: "Luật",
    authority: "Quốc hội",
    date: "2026-10-28",
    status: "ready",
    saved: false,
    sample: true,
  },
  {
    id: "sample-3",
    title: "Bộ luật Dân sự",
    number: "91/2015/QH13",
    category: "Bộ luật",
    authority: "Quốc hội",
    date: "2026-10-27",
    status: "ready",
    saved: false,
    sample: true,
  },
  {
    id: "sample-4",
    title: "Luật Bảo vệ dữ liệu cá nhân",
    number: "Tài liệu nghiên cứu",
    category: "Luật",
    authority: "Thư viện nội bộ",
    date: "2026-10-26",
    status: "uploaded",
    saved: true,
    sample: true,
  },
  {
    id: "sample-5",
    title: "Luật Giao dịch điện tử",
    number: "20/2023/QH15",
    category: "Luật",
    authority: "Quốc hội",
    date: "2026-10-25",
    status: "ready",
    saved: false,
    sample: true,
  },
];
const $ = (selector) => document.querySelector(selector);
const state = {
  documents: readStorage(DOCUMENT_KEY, sampleDocuments, isDocument),
  chats: readStorage(CHAT_KEY, [], isChat),
  view: "chat",
  category: "Tất cả",
  chatId: null,
  documentId: null,
};
const pdfUrls = new Map();
let uploadFile = null;
let toastTimer;

// Kiểm tra và lưu dữ liệu trên trình duyệt
function isDocument(value) {
  return (
    value &&
    ["id", "title", "number", "category", "authority", "date"].every(
      (key) => typeof value[key] === "string",
    ) &&
    !Number.isNaN(Date.parse(value.date))
  );
}

function isChat(value) {
  return (
    value &&
    typeof value.id === "string" &&
    typeof value.title === "string" &&
    Array.isArray(value.notes) &&
    value.notes.every((note) => typeof note === "string")
  );
}

function readStorage(key, fallback, validate) {
  try {
    const value = JSON.parse(localStorage.getItem(key));
    if (Array.isArray(value) && value.every(validate)) return value;
  } catch {
    /* Trình duyệt có thể chặn localStorage. */
  }
  return structuredClone(fallback);
}

function persist() {
  try {
    localStorage.setItem(DOCUMENT_KEY, JSON.stringify(state.documents));
    localStorage.setItem(CHAT_KEY, JSON.stringify(state.chats));
  } catch {
    notify("Không thể lưu thay đổi vào trình duyệt. Hãy kiểm tra dung lượng lưu trữ.");
  }
  renderCounts();
}

// Thông báo và tạo phần tử giao diện
function notify(message) {
  clearTimeout(toastTimer);
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  toastTimer = setTimeout(() => {
    $("#toast").hidden = true;
  }, 4500);
}

// Dùng textContent cho dữ liệu người dùng, không chèn HTML từ tên file/câu hỏi.
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderCounts() {
  $("#document-count").textContent = state.documents.length;
  $("#saved-count").textContent = state.documents.filter((doc) => doc.saved).length;
  $("#chat-count").textContent = state.chats.length;
}

// Điều hướng và hỏi đáp, chưa kết nối AI
function closeMenu() {
  $("#sidebar").classList.remove("is-open");
  $("#menu-overlay").hidden = true;
  $("#menu-toggle").setAttribute("aria-expanded", "false");
}

function navigate(view) {
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
  if (view === "library" || view === "saved") renderDocuments();
  closeMenu();
}

function newChat() {
  state.chatId = null;
  $("#question-form").reset();
  renderChat();
  navigate("chat");
  $("#question").focus();
}

function renderChat() {
  const active = state.chats.find((chat) => chat.id === state.chatId);
  const hasQuestions = Boolean(active?.notes.length);
  $("#history-bar").hidden = state.chats.length === 0;
  $("#history-select").replaceChildren(new Option("Chọn cuộc trò chuyện", ""));
  state.chats.forEach((chat) =>
    $("#history-select").add(new Option(chat.title || "Chưa đặt tên", chat.id)),
  );
  $("#history-select").value = active?.id || "";
  $("#delete-chat").hidden = !active;
  $("#welcome").hidden = hasQuestions;
  $("#suggestions").hidden = hasQuestions;
  $("#conversation").hidden = !hasQuestions;
  $("#chat-title").value = active?.title || "";
  $("#messages").replaceChildren();
  active?.notes.forEach((note) => {
    const bubble = element("div", "question-message");
    bubble.append(element("span", "", "Bạn"), element("p", "", note));
    $("#messages").append(bubble);
  });
  $("#messages").scrollTop = $("#messages").scrollHeight;
  $("#send-question").disabled = !$("#question").value.trim();
}

$("#question-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const question = $("#question").value.trim();
  if (!question) return;
  let active = state.chats.find((chat) => chat.id === state.chatId);
  if (!active) {
    active = {
      id: crypto.randomUUID(),
      title: question.slice(0, 70),
      date: new Date().toISOString(),
      notes: [],
    };
    state.chats.unshift(active);
    state.chatId = active.id;
  }
  active.notes.push(question);
  $("#question-form").reset();
  persist();
  renderChat();
  $("#question").focus();
});
$("#question").addEventListener("input", () => {
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
  const active = state.chats.find((chat) => chat.id === state.chatId);
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

// Tìm kiếm, lọc và đánh dấu tài liệu
function renderDocuments() {
  $("#library-title").textContent =
    state.view === "saved" ? "Tài liệu đã lưu" : "Thư viện tài liệu";
  const query = $("#search").value.trim().toLocaleLowerCase("vi");
  const pool = state.documents.filter((doc) => state.view !== "saved" || doc.saved);
  const sortByName = $("#sort").value === "name";
  const filtered = pool.filter(
    (doc) =>
      (state.category === "Tất cả" || doc.category === state.category) &&
      `${doc.title} ${doc.number} ${doc.authority}`.toLocaleLowerCase("vi").includes(query),
  );
  filtered.sort((a, b) =>
    sortByName ? a.title.localeCompare(b.title, "vi") : b.date.localeCompare(a.date),
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
    statusCell.append(
      element(
        "span",
        `status-badge ${doc.status === "ready" ? "ready" : "uploaded"}`,
        doc.status === "ready" ? "Sẵn sàng xem" : "Đã thêm",
      ),
    );
    const actions = element("td");
    const bookmark = element("button", "text-button", doc.saved ? "Bỏ lưu" : "Lưu");
    bookmark.setAttribute("aria-label", `${doc.saved ? "Bỏ lưu" : "Lưu"} ${doc.title}`);
    bookmark.addEventListener("click", () => toggleSaved(doc.id));
    const open = element("button", "text-button", "Xem");
    open.setAttribute("aria-label", `Xem ${doc.title}`);
    open.addEventListener("click", () => openDocument(doc.id));
    actions.append(bookmark, open);
    row.append(
      titleCell,
      element("td", "", doc.category),
      element("td", "date-cell", new Date(doc.date).toLocaleDateString("vi-VN")),
      statusCell,
      actions,
    );
    $("#document-rows").append(row);
  });
  $("#empty-library").hidden = filtered.length > 0;
  $("#result-count").textContent = `Hiển thị ${filtered.length} / ${pool.length} tài liệu`;
}

function toggleSaved(id) {
  const doc = state.documents.find((item) => item.id === id);
  if (!doc) return;
  doc.saved = !doc.saved;
  persist();
  renderDocuments();
  $("#detail-bookmark").textContent = doc.saved ? "Bỏ đánh dấu" : "Đánh dấu";
}

$("#search").addEventListener("input", renderDocuments);
$("#sort").addEventListener("change", renderDocuments);
$("#category-tabs").addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (!button) return;
  state.category = button.dataset.category;
  document.querySelectorAll("[data-category]").forEach((tab) => {
    const selected = tab === button;
    tab.classList.toggle("selected", selected);
    tab.setAttribute("aria-pressed", String(selected));
  });
  renderDocuments();
});

// Kiểm tra và đọc PDF trong phiên hiện tại
async function validatePdf(file) {
  if (!file) return "Hãy chọn file PDF.";
  if (!file.name.toLowerCase().endsWith(".pdf") || (file.type && file.type !== "application/pdf"))
    return "Vui lòng chọn đúng file PDF.";
  if (file.size > 20 * 1024 * 1024) return "PDF vượt quá giới hạn 20 MB.";
  if ((await file.slice(0, 5).text()) !== "%PDF-") return "File không có định dạng PDF hợp lệ.";
  return null;
}

function setPdf(id, file) {
  if (pdfUrls.has(id)) URL.revokeObjectURL(pdfUrls.get(id));
  pdfUrls.set(id, URL.createObjectURL(file));
}

function openDocument(id) {
  const doc = state.documents.find((item) => item.id === id);
  if (!doc) return;
  state.documentId = id;
  $("#pdf-error").textContent = "";
  $("#detail-title").textContent = doc.title;
  $("#detail-meta").textContent = `${doc.number} · ${doc.authority}`;
  $("#detail-bookmark").textContent = doc.saved ? "Bỏ đánh dấu" : "Đánh dấu";
  const url = pdfUrls.get(id);
  $("#pdf-viewer").hidden = !url;
  $("#pdf-empty").hidden = Boolean(url);
  $("#download-pdf").hidden = !url;
  if (url) {
    $("#pdf-viewer").src = url;
    $("#download-pdf").href = url;
    $("#download-pdf").download = `${doc.title}.pdf`;
  } else {
    $("#pdf-viewer").removeAttribute("src");
    $("#download-pdf").removeAttribute("href");
  }
  $("#pdf-empty-title").textContent = doc.sample
    ? "Bản ghi minh họa thư viện"
    : "Chọn lại PDF để đọc";
  $("#pdf-empty-note").textContent = doc.sample
    ? "Bản ghi mẫu chỉ có metadata, không đính kèm văn bản gốc. Chọn PDF của bạn để trải nghiệm trình đọc."
    : "PDF không được lưu sau khi tải lại trang. Vui lòng chọn lại file từ thiết bị.";
  if (!$("#document-dialog").open) $("#document-dialog").showModal();
}

$("#open-upload").addEventListener("click", () => {
  $("#upload-form").reset();
  uploadFile = null;
  $("#file-label").textContent = "Chọn hoặc kéo thả PDF vào đây";
  $("#upload-error").textContent = "";
  $("#upload-dialog").showModal();
});
function selectUploadFile(file) {
  uploadFile = file || null;
  $("#file-label").textContent = file
    ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`
    : "Chọn hoặc kéo thả PDF vào đây";
  $("#upload-error").textContent = "";
}
$("#pdf-file").addEventListener("change", (event) => selectUploadFile(event.target.files[0]));
$("#drop-zone").addEventListener("dragover", (event) => event.preventDefault());
$("#drop-zone").addEventListener("drop", (event) => {
  event.preventDefault();
  selectUploadFile(event.dataTransfer.files[0]);
});
$("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const file = uploadFile;
  $("#save-document").disabled = true;
  try {
    const error = await validatePdf(file);
    if (error) {
      $("#upload-error").textContent = error;
      return;
    }
    const data = new FormData(form);
    const title = String(data.get("title")).trim();
    if (!title) {
      $("#upload-error").textContent = "Vui lòng nhập tên tài liệu.";
      return;
    }
    const doc = {
      id: crypto.randomUUID(),
      title,
      number: String(data.get("number")).trim() || "Chưa có số hiệu",
      category: String(data.get("category")),
      authority: String(data.get("authority")).trim() || "Tài liệu cá nhân",
      date: new Date().toISOString(),
      status: "uploaded",
      saved: false,
    };
    setPdf(doc.id, file);
    state.documents.unshift(doc);
    persist();
    renderDocuments();
    $("#upload-dialog").close();
    notify("Đã thêm PDF vào phiên trải nghiệm. File chưa được gửi lên Firebase.");
  } catch {
    $("#upload-error").textContent = "Không đọc được file. Vui lòng chọn lại PDF.";
  } finally {
    $("#save-document").disabled = false;
  }
});
$("#reselect-pdf").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  const id = state.documentId;
  if (!file) return;
  try {
    const error = await validatePdf(file);
    if (error) {
      $("#pdf-error").textContent = error;
      return;
    }
    if (!state.documents.some((doc) => doc.id === id)) return;
    setPdf(id, file);
    openDocument(id);
  } catch {
    $("#pdf-error").textContent = "Không đọc được PDF. Hãy chọn lại file.";
  } finally {
    event.target.value = "";
  }
});
$("#detail-bookmark").addEventListener("click", () => toggleSaved(state.documentId));
$("#delete-document").addEventListener("click", () => {
  state.documents = state.documents.filter((doc) => doc.id !== state.documentId);
  if (pdfUrls.has(state.documentId)) URL.revokeObjectURL(pdfUrls.get(state.documentId));
  pdfUrls.delete(state.documentId);
  $("#document-dialog").close();
  persist();
  renderDocuments();
  notify("Đã xóa tài liệu khỏi thư viện trải nghiệm.");
});
$("#document-dialog").addEventListener("close", () => {
  $("#pdf-viewer").removeAttribute("src");
});

// Sự kiện chung và khởi tạo trang
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
  state.documents = structuredClone(sampleDocuments);
  state.chats = [];
  state.chatId = null;
  pdfUrls.forEach(URL.revokeObjectURL);
  pdfUrls.clear();
  persist();
  renderChat();
  notify("Đã khôi phục dữ liệu mẫu.");
});
window.addEventListener("beforeunload", () => pdfUrls.forEach(URL.revokeObjectURL));
renderCounts();
renderChat();
navigate("chat");
