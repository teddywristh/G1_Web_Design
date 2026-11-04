import { api } from "./api.js";
import {
  $,
  ACTION_TEXT,
  PROCESSING_TEXT,
  STAGE_TEXT,
  element,
  isAdmin,
  notify,
  persist,
  renderCounts,
  state,
} from "./core.js";
import { currentKb } from "./knowledge-bases.js";

let blobUrl = null;
let documentRevision = 0;

// Danh sách tài liệu trong kho chung và kho riêng
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
    documentType: raw.documentType,
    issueDate: raw.issueDate,
    effectiveDate: raw.effectiveDate,
    status: raw.status,
    sourceUrl: raw.sourceUrl,
  };
}

async function loadDocs(reset) {
  const kb = currentKb();
  if (!kb || !state.user) return;
  const revision = ++documentRevision;
  const userId = state.user.id;
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
    if (revision !== documentRevision || state.user?.id !== userId || state.kbId !== kb.id) return;
    state.docs.push(...page.items.map((item) => normalizeDoc(item, kb)));
    state.nextCursor = page.nextCursor;
  } catch (error) {
    if (revision !== documentRevision || state.user?.id !== userId) return;
    notify(error.message);
  }
  renderDocuments();
  if (kb.kind === "private") refreshProcessing();
}

async function refreshProcessing() {
  clearTimeout(state.pollTimer);
  if (!state.user || state.view !== "library" || document.hidden) return;
  const userId = state.user.id;
  const revision = documentRevision;
  const pending = state.docs.filter((doc) => !doc.shared);
  await Promise.all(
    pending.map(async (doc) => {
      try {
        const processing = await api.get(
          `/knowledge-bases/${doc.kbId}/documents/${doc.id}/processing`,
        );
        if (revision === documentRevision && state.user?.id === userId) doc.processing = processing;
      } catch {
        if (revision === documentRevision && state.user?.id === userId)
          doc.processing = { status: "status_unavailable" };
      }
    }),
  );
  if (revision !== documentRevision || state.user?.id !== userId) return;
  if (state.view === "library") {
    document.querySelectorAll("[data-processing-doc]").forEach((cell) => {
      const doc = state.docs.find((item) => item.id === cell.dataset.processingDoc);
      if (doc) cell.replaceChildren(processingContent(doc));
    });
  }
  const busy = pending.some((doc) =>
    ["queued", "processing", "status_unavailable"].includes(doc.processing?.status),
  );
  if (busy && state.view === "library" && !document.hidden) {
    state.pollTimer = setTimeout(refreshProcessing, 2000);
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
  const status =
    doc.fileState === "upload_failed" ? "failed" : doc.processing?.status || "status_unavailable";
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

// Cập nhật tiến độ mà không dựng lại các nút trong bảng
function processingContent(doc) {
  const content = document.createDocumentFragment();
  content.append(statusBadge(doc));
  const progress = doc.processing?.embeddingProgress;
  const busy = ["queued", "processing"].includes(doc.processing?.status);
  if (busy || progress || doc.processing?.status === "ready") {
    const bar = element("progress", "embedding-progress");
    bar.max = 100;
    const completed = Number(progress?.completed);
    const total = Number(progress?.total);
    const measured =
      Number.isFinite(completed) && completed >= 0 && Number.isFinite(total) && total > 0;
    const ready = doc.processing?.status === "ready";
    const percent = ready
      ? 100
      : measured
        ? Math.min(100, Math.round((completed / total) * 100))
        : null;
    if (percent !== null) bar.value = percent;
    bar.setAttribute("aria-label", `Tiến độ xử lý ${doc.title}`);
    const label = ready
      ? "Đã lập chỉ mục · 100%"
      : measured
        ? `Embedding ${percent}% · ${completed}/${total} đoạn`
        : "Đang xử lý · chờ số liệu tiến độ từ máy chủ";
    content.append(bar, element("small", "embedding-progress-label", label));
  }
  if (processingNote(doc)) {
    content.append(element("small", "processing-detail", processingNote(doc)));
  }
  return content;
}

function renderDocuments() {
  $("#library-title").textContent = "Thư viện tài liệu";
  const query = $("#search").value.trim().toLocaleLowerCase("vi");
  const pool = state.docs;
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
    statusCell.dataset.processingDoc = doc.id;
    statusCell.append(processingContent(doc));
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

// Đọc PDF, xử lý lại và xóa tài liệu
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
  $("#detail-meta").textContent = [doc.number, doc.authority, coverageNote(doc)]
    .filter(Boolean)
    .join(" · ");
  $("#detail-bookmark").textContent = state.saved.has(id) ? "Bỏ đánh dấu" : "Đánh dấu";
  $("#delete-document").hidden = doc.shared && !isAdmin();
  $("#edit-document").hidden = !doc.shared || !isAdmin();
  $("#shared-edit-form").hidden = true;
  if (doc.shared) {
    const form = $("#shared-edit-form");
    Object.entries({
      title: doc.title,
      documentType: doc.documentType,
      documentNumber: doc.number,
      issuingAuthority: doc.authority,
      issueDate: doc.issueDate,
      effectiveDate: doc.effectiveDate || "",
      status: doc.status,
      sourceUrl: doc.sourceUrl || "",
    }).forEach(([name, value]) => {
      form.elements[name].value = value || "";
    });
  }
  const status = doc.processing;
  $("#retry-document").hidden = !(
    status &&
    (status.retryable || status.status === "needs_ocr" || status.status === "ready")
  );
  $("#pdf-viewer").hidden = true;
  $("#pdf-empty").hidden = false;
  $("#pdf-empty-title").textContent = "Đang tải PDF…";
  $("#pdf-empty-note").textContent = status?.nextAction ? ACTION_TEXT[status.nextAction] || "" : "";
  if (!$("#document-dialog").open) $("#document-dialog").showModal();
  if (doc.fileState === "upload_failed") {
    $("#pdf-empty-title").textContent = "PDF chưa được tải lên";
    $("#pdf-empty-note").textContent = ACTION_TEXT.check_storage;
    $("#download-pdf").hidden = true;
    return;
  }
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
$("#edit-document").addEventListener("click", () => {
  $("#shared-edit-form").hidden = false;
  $("#edit-document").hidden = true;
});
$("#cancel-edit-document").addEventListener("click", () => {
  $("#shared-edit-form").hidden = true;
  $("#edit-document").hidden = false;
});
$("#shared-edit-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const doc = state.docs.find((item) => item.id === state.documentId);
  if (!doc) return;
  const data = new FormData(event.currentTarget);
  const body = Object.fromEntries(data.entries());
  body.effectiveDate ||= null;
  body.sourceUrl ||= null;
  try {
    const updated = await api.patch(`/admin/documents/${doc.id}`, body, { version: doc.version });
    Object.assign(doc, normalizeDoc(updated, { id: doc.kbId, kind: "shared" }));
    $("#shared-edit-form").hidden = true;
    $("#edit-document").hidden = false;
    $("#detail-title").textContent = doc.title;
    $("#detail-meta").textContent = [doc.number, doc.authority].filter(Boolean).join(" · ");
    renderDocuments();
    notify("Đã cập nhật thông tin tài liệu.");
  } catch (error) {
    $("#pdf-error").textContent = error.message;
  }
});
$("#delete-document").addEventListener("click", async () => {
  const doc = state.docs.find((item) => item.id === state.documentId);
  if (!doc || !confirm(`Xóa "${doc.title}"? Tài liệu sẽ ngừng được dùng để trả lời ngay.`)) return;
  try {
    await api.del(
      doc.shared
        ? `/admin/documents/${doc.id}`
        : `/knowledge-bases/${doc.kbId}/documents/${doc.id}`,
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

// Cập nhật trạng thái khi người dùng quay lại tab
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state.view === "library") refreshProcessing();
});

export { loadDocs, renderDocuments };
