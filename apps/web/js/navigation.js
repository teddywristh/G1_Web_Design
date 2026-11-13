import { setAuthMode, showAuth } from "./auth.js";
import { $, isAdmin, state } from "./core.js";
import { loadDocs, renderDocuments } from "./documents.js";
import { closeEvidence } from "./evidence.js";
import { loadKbs, renderKbControls } from "./knowledge-bases.js";
import { loadSessions } from "./sessions.js";
import { loadConnections } from "./settings.js";
import { loadAdmin } from "./admin.js";

// Điều hướng giữa không gian làm việc và thiết lập
function closeMenu() {
  $("#sidebar").classList.remove("is-open");
  $("#menu-overlay").hidden = true;
  $("#menu-toggle").setAttribute("aria-expanded", "false");
}

function navigate(view, settingsPage = "account") {
  if (view === "settings" && !state.user) {
    setAuthMode("login");
    showAuth("Đăng nhập để quản lý tài khoản và kết nối AI.");
    return;
  }
  if (!["chat", "library", "settings"].includes(view)) return;
  closeEvidence(false);
  state.view = view;
  const settings = view === "settings";
  document.body.classList.toggle("settings-mode", settings);
  $("#workspace-nav").hidden = settings;
  $("#settings-nav").hidden = !settings;
  $("#settings-back").hidden = !settings;
  document.querySelectorAll(".view").forEach((section) => {
    section.hidden = section.id !== `${view}-view`;
  });
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
    if (button.dataset.view === view) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  $("#page-label").textContent = {
    chat: "Hỏi đáp",
    library: "Thư viện tài liệu",
    settings: "Thiết lập",
  }[view];
  const footnote = {
    chat: "Hỏi đáp: câu trả lời có thể có sai sót; hãy kiểm tra nguồn trước khi sử dụng.",
    library: "Thư viện: tài liệu và metadata chỉ mang tính tham khảo, cần đối chiếu bản gốc.",
    settings: {
      account: "Tài khoản: lịch sử hội thoại được lưu trên thiết bị này và có thể xóa bất cứ lúc nào.",
      ai: "Kết nối AI: khóa API được xử lý qua máy chủ; không chia sẻ khóa với người khác.",
      admin: "Quản trị: các thao tác quản trị có thể ảnh hưởng đến người dùng và tài liệu dùng chung.",
    },
  };
  if (settings) {
    state.settingsPage =
      settingsPage === "ai" || (settingsPage === "admin" && isAdmin()) ? settingsPage : "account";
    const account = state.settingsPage === "account";
    const admin = state.settingsPage === "admin";
    $("#account-card").hidden = !account;
    $("#ai-card").hidden = account || admin;
    $("#admin-card").hidden = !admin;
    $("#settings-title").textContent = account
      ? "Tài khoản"
      : admin
        ? "Quản trị hệ thống"
        : "Kết nối AI";
    $("#settings-description").textContent = account
      ? "Thông tin cá nhân, bảo mật và thiết bị đăng nhập."
      : admin
        ? "Quản lý người dùng, tài liệu dùng chung và nhật ký hệ thống."
        : "Quản lý kết nối và khóa của những nhà cung cấp bạn sử dụng.";
    document.querySelectorAll("[data-settings-page]").forEach((button) => {
      const active = button.dataset.settingsPage === state.settingsPage;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    $("#route-footnote").textContent = footnote.settings[state.settingsPage];
    if (account) loadSessions();
    else if (admin) loadAdmin();
    else loadConnections();
  } else if (view === "library") {
    $("#route-footnote").textContent = footnote.library;
    if (state.user) loadDocs(true);
    else {
      renderKbControls();
      renderDocuments();
    }
  } else if (state.user) loadKbs();
  if (view === "chat") $("#route-footnote").textContent = footnote.chat;
  closeMenu();
}

export { closeMenu, navigate };
