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
