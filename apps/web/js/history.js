import { $, element, persist, state } from "./core.js";
import { navigate } from "./navigation.js";

// Lịch sử hội thoại trong sidebar
function removeChat(id) {
  if (!confirm("Xóa cuộc trò chuyện này trên thiết bị?")) return;
  state.chats = state.chats.filter(chat => chat.id !== id);
  if (state.chatId === id) state.chatId = null;
  if (state.pendingChat?.chatId === id) state.pendingChat = null;
  persist();
  document.dispatchEvent(new Event("chat-selected"));
}

function renderHistory() {
  const list = $("#history-list");
  list.replaceChildren();
  $("#history-empty").hidden = state.chats.length > 0;
  const today = new Date().toDateString();
  let previousGroup = null;
  state.chats.forEach((chat) => {
    const group = new Date(chat.date).toDateString() === today ? "Hôm nay" : "Trước đó";
    if (group !== previousGroup) list.append(element("p", "history-group", group));
    previousGroup = group;
    const row = element("div", "history-item");
    const button = element("button", "history-title", chat.title || "Chưa đặt tên");
    button.title = chat.title || "Chưa đặt tên";
    if (chat.id === state.chatId) button.setAttribute("aria-current", "page");
    button.addEventListener("click", () => {
      state.chatId = chat.id;
      document.dispatchEvent(new Event("chat-selected"));
      navigate("chat");
    });
    const remove = element("button", "history-delete", "Xóa");
    remove.setAttribute("aria-label", `Xóa hội thoại ${chat.title}`);
    remove.addEventListener("click", () => removeChat(chat.id));
    row.append(button, remove);
    list.append(row);
  });
}

export { renderHistory, removeChat };
