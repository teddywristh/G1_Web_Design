import { setAuthMode, showAuth } from "./auth.js";
import { $, state } from "./core.js";
import { loadDocs, renderDocuments } from "./documents.js";
import { closeEvidence } from "./evidence.js";
import { loadKbs, renderKbControls } from "./knowledge-bases.js";
import { loadSessions } from "./sessions.js";
import { loadConnections } from "./settings.js";

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
  if (settings) {
    state.settingsPage = settingsPage === "ai" ? "ai" : "account";
    const account = state.settingsPage === "account";
    $("#account-card").hidden = !account;
    $("#ai-card").hidden = account;
    $("#settings-title").textContent = account ? "Tài khoản" : "Kết nối AI";
    $("#settings-description").textContent = account
      ? "Thông tin cá nhân, bảo mật và thiết bị đăng nhập."
      : "Quản lý kết nối và khóa của những nhà cung cấp bạn sử dụng.";
    document.querySelectorAll("[data-settings-page]").forEach((button) => {
      const active = button.dataset.settingsPage === state.settingsPage;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    if (account) loadSessions();
    else loadConnections();
  } else if (view === "library") {
    if (state.user) loadDocs(true);
    else {
      renderKbControls();
      renderDocuments();
    }
  } else if (state.user) loadKbs();
  closeMenu();
}

export { closeMenu, navigate };
