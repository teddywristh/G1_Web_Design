import { api } from "./api.js";
import { $, limitText } from "./core.js";

let pdfUrl = null;
let revision = 0;
let returnFocus = null;

function releasePdf() {
  $("#evidence-pdf").removeAttribute("src");
  $("#evidence-pdf").hidden = true;
  if (pdfUrl) URL.revokeObjectURL(pdfUrl);
  pdfUrl = null;
}

function closeEvidence(restoreFocus = true) {
  revision++;
  releasePdf();
  $("#evidence-panel").hidden = true;
  $("#app-shell").classList.remove("evidence-open");
  if (restoreFocus && returnFocus?.isConnected) returnFocus.focus();
}

// Panel nguồn cạnh hội thoại và PDF đúng trang trích dẫn
async function openEvidence(citation) {
  const current = ++revision;
  returnFocus = document.activeElement;
  releasePdf();
  $("#evidence-panel").hidden = false;
  $("#app-shell").classList.add("evidence-open");
  $("#evidence-title").textContent = citation.document_title;
  $("#evidence-title").focus({ preventScroll: true });
  $("#evidence-text").textContent = citation.quote || "";
  $("#evidence-meta").textContent = "Đang tải nguồn…";
  for (const id of ["evidence-error", "evidence-limits", "evidence-pdf-status"])
    $(`#${id}`).textContent = "";
  $("#evidence-link").hidden = true;
  $("#evidence-pdf-open").hidden = true;
  if (!citation.provision_version_id) {
    $("#evidence-meta").textContent = "Nguồn web · hiệu lực chưa được xác minh";
    try {
      const url = new URL(citation.source_url);
      if (url.protocol === "https:" && !url.username && !url.password) {
        $("#evidence-link").href = url.href;
        $("#evidence-link").hidden = false;
      }
    } catch {
      /* Nguồn không có URL hợp lệ */
    }
    return;
  }
  try {
    const path = `/evidence/${encodeURIComponent(citation.provision_version_id)}`;
    const item = await api.get(path);
    if (revision !== current) return;
    $("#evidence-title").textContent = [item.documentTitle, item.documentNumber]
      .filter(Boolean)
      .join(" · ");
    $("#evidence-meta").textContent = [
      item.article,
      item.clause,
      `Trang ${item.pageStart}–${item.pageEnd}`,
    ]
      .filter(Boolean)
      .join(" · ");
    $("#evidence-text").textContent = item.text;
    $("#evidence-limits").textContent = (item.limitations || []).map(limitText).join(" · ");
    const loadPdf = async () => {
      $("#evidence-pdf-status").textContent = "Đang tải PDF…";
      $("#evidence-pdf-open").disabled = true;
      try {
        const blob = await api.blob(`${path}/pdf`);
        if (revision !== current) return;
        releasePdf();
        pdfUrl = URL.createObjectURL(blob);
        $("#evidence-pdf").src = `${pdfUrl}#page=${Math.max(1, Number(item.pageStart) || 1)}`;
        $("#evidence-pdf").hidden = false;
        $("#evidence-pdf-status").textContent = "";
      } catch (error) {
        if (revision === current) $("#evidence-pdf-status").textContent = error.message;
      } finally {
        if (revision === current) $("#evidence-pdf-open").disabled = false;
      }
    };
    $("#evidence-pdf-open").hidden = false;
    $("#evidence-pdf-open").onclick = loadPdf;
    await loadPdf();
  } catch (error) {
    if (revision !== current) return;
    $("#evidence-meta").textContent = "Không tải được nguồn";
    $("#evidence-error").textContent =
      error.status === 404
        ? "Nguồn đã bị xóa, thu hồi hoặc không còn quyền truy cập."
        : error.message;
  }
}

$("#close-evidence").addEventListener("click", () => closeEvidence());
document.addEventListener("close-evidence", () => closeEvidence(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("#evidence-panel").hidden) closeEvidence();
});

export { openEvidence, closeEvidence };
