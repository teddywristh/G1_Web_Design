import { api } from "./api.js";
import { $, notify, state } from "./core.js";
import { loadDocs } from "./documents.js";
import { currentKb, loadKbs } from "./knowledge-bases.js";

// Chọn PDF và tải lên theo loại kho
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
  ["number", "authority", "issueDate"].forEach((name) => {
    $(`#shared-fields [name="${name}"]`).required = shared;
  });
  $("#upload-public-label").hidden = !state.aiOptions?.embedding?.requiresPublicInput;
  $("#upload-public-confirm").required = Boolean(state.aiOptions?.embedding?.requiresPublicInput);
  $("#upload-notice").textContent = shared
    ? "Văn bản dùng chung. Sau khi xử lý xong, hãy xuất bản bản dựng mới để mọi người tra cứu được."
    : "Chỉ bạn xem được tài liệu này. Khi trạng thái là Sẵn sàng tra cứu, tài liệu sẽ tự động được dùng khi hỏi đáp.";
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
      $("#upload-error").textContent =
        "Xác nhận tài liệu không chứa dữ liệu cá nhân hoặc thông tin mật trước khi xử lý.";
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
