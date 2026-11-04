import "./upload.js";
import { boot } from "./auth.js";
import { newChat, renderChat } from "./chat.js";
import { $, notify, persist, state } from "./core.js";
import { closeMenu, navigate } from "./navigation.js";

// Khởi tạo và sự kiện dùng chung
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
$("#profile-button").addEventListener("click", () => navigate("settings", "account"));
$("#settings-back").addEventListener("click", () => navigate("chat"));
document.querySelectorAll("[data-settings-page]").forEach((button) => {
  button.addEventListener("click", () => navigate("settings", button.dataset.settingsPage));
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeMenu();
    $(".query-options").open = false;
  }
});
document.addEventListener("click", (event) => {
  const options = $(".query-options");
  if (!options.contains(event.target)) options.open = false;
});
$("#reset-data").addEventListener("click", () => {
  if (!confirm("Xóa lịch sử hội thoại trên trình duyệt này?")) return;
  state.chats = [];
  state.chatId = null;
  state.pendingChat = null;
  persist();
  renderChat();
  notify("Đã xóa lịch sử hội thoại trên thiết bị.");
});

boot();
