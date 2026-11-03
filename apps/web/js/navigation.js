import { setAuthMode, showAuth } from "./auth.js";
import { $, state } from "./core.js";
import { loadDocs, renderDocuments } from "./documents.js";
import { loadKbs, renderKbControls } from "./knowledge-bases.js";
import { loadSessions } from "./sessions.js";
import { loadConnections } from "./settings.js";

// Chuyển trang và đóng menu
function closeMenu() {
  $("#sidebar").classList.remove("is-open");
  $("#menu-overlay").hidden = true;
  $("#menu-toggle").setAttribute("aria-expanded", "false");
}

function navigate(view) {
  if (view === "settings" && !state.user) {
    setAuthMode("login");
    showAuth("Đăng nhập để quản lý tài khoản và kết nối AI.");
    return;
  }
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
    else {
      renderKbControls();
      renderDocuments();
    }
  }
  if (view === "settings") {
    loadConnections();
    loadSessions();
  }
  if (view === "chat" && state.user) loadKbs();
  closeMenu();
}

export { closeMenu, navigate };
