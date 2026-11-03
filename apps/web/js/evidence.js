import { api } from "./api.js";
import { $, limitText } from "./core.js";

// Mở đoạn nguồn sau khi backend kiểm tra quyền truy cập
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
    const place = [item.chapter && `Chương ${item.chapter}`, item.article, item.clause].filter(
      Boolean,
    );
    const pages =
      item.pageStart === item.pageEnd
        ? `trang ${item.pageStart}`
        : `trang ${item.pageStart}–${item.pageEnd}`;
    $("#evidence-title").textContent =
      `${item.documentTitle}${item.documentNumber ? " · " + item.documentNumber : ""}`;
    $("#evidence-meta").textContent = `${place.join(" · ")} · ${pages} của PDF`;
    $("#evidence-text").textContent = item.text;
    $("#evidence-limits").textContent = item.limitations.map(limitText).join(" · ");
  } catch (error) {
    $("#evidence-error").textContent =
      error.status === 404
        ? "Nguồn này không còn truy cập được (đã xóa hoặc thu hồi)."
        : error.message;
  }
}

export { openEvidence };
