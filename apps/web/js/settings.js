import { api } from "./api.js";
import { $, element, isAdmin, notify, state } from "./core.js";
import { loadModels } from "./models.js";
let connectionsRevision = 0;

// Khóa API và kết nối AI; việc chọn model nằm ở models.js
function renderConnectionSummary() {
  const saved = state.connections.filter((item) => item.configured && item.enabled).length;
  const chatgpt = state.chatgpt.connected ? "ChatGPT đã kết nối." : "ChatGPT chưa kết nối.";
  $("#connection-summary").textContent =
    `${chatgpt} ${saved ? `${saved} khóa API đang bật.` : "Chưa lưu khóa API."}`;
}

function renderChatgpt() {
  const connection = state.chatgpt;
  $("#chatgpt-status").textContent = !connection.available
    ? "ChatGPT qua OpenCode chưa được bật trên máy chủ."
    : connection.connected
      ? "Đã kết nối ChatGPT cho phiên của bạn."
      : connection.pending
        ? connection.url
          ? "Đang chờ đăng nhập ChatGPT."
          : "Phiên đăng nhập đang chờ. Hãy ngắt kết nối và bắt đầu lại để nhận mã mới."
        : "Chưa kết nối.";
  $("#chatgpt-instructions").hidden = !connection.instructions;
  $("#chatgpt-instructions").textContent = connection.instructions || "";
  $("#chatgpt-link").hidden = !connection.url;
  if (connection.url) $("#chatgpt-link").href = connection.url;
  else $("#chatgpt-link").removeAttribute("href");
  $("#chatgpt-start").hidden = !connection.available || connection.connected || connection.pending;
  $("#chatgpt-finish").hidden = !connection.pending || !connection.url;
  $("#chatgpt-disconnect").hidden = !connection.connected && !connection.pending;
  renderConnectionSummary();
}

async function loadConnections() {
  if (!state.user) return;
  const userId = state.user.id;
  const revision = ++connectionsRevision;
  try {
    const options = await api.get("/ai/connections");
    if (state.user?.id !== userId || revision !== connectionsRevision) return;
    state.aiOptions = options;
    state.connections = options.connections;
    const available = Boolean(
      options.methods?.find((item) => item.id === "chatgpt_oauth")?.available,
    );
    if (available) {
      const status = await api.get("/ai/chatgpt");
      if (state.user?.id !== userId || revision !== connectionsRevision) return;
      state.chatgpt = { ...state.chatgpt, ...status, available };
    } else {
      state.chatgpt = { available: false, connected: false, pending: false };
    }
  } catch (error) {
    if (state.user?.id !== userId || revision !== connectionsRevision) return;
    notify(error.message);
    return;
  }
  const list = $("#connection-list");
  list.replaceChildren();
  renderChatgpt();
  const embedding = state.aiOptions?.embedding;
  $("#query-public-label").hidden = !embedding?.requiresPublicInput;
  $("#embedding-info").textContent =
    embedding?.provider === "local"
      ? `Embedding chạy trên GPU local (${embedding.model}); không cần khóa OpenRouter.`
      : embedding?.provider === "openrouter"
        ? `Embedding dùng OpenRouter (${embedding.model || "chưa chọn model"}) với key chung do hệ thống cấu hình${embedding.configured ? "." : "; chưa cấu hình đầy đủ."}`
        : "Embedding dùng khóa OpenAI; nếu không có khóa OpenAI, hệ thống chỉ tra theo số hiệu/điều.";
  $("#connection-scope option[value=shared]").hidden = !isAdmin();
  const names = {
    openai: "OpenAI",
    anthropic: "Claude",
    deepseek: "DeepSeek",
    openrouter: "OpenRouter",
  };
  state.connections
    .filter((item) => names[item.provider])
    .forEach((item) => {
      const row = element("li");
      const scope = item.scope === "personal" ? "cá nhân" : "dùng chung";
      row.append(element("span", "", `${names[item.provider]} API · ${scope}: `));
      row.append(
        element(
          "strong",
          "",
          item.configured ? (item.enabled ? "đã lưu khóa" : "đang tắt") : "chưa lưu khóa",
        ),
      );
      if ((item.scope === "personal" || isAdmin()) && item.origin === "stored" && item.configured) {
        const remove = element("button", "text-button danger", "Xóa");
        remove.addEventListener("click", async () => {
          try {
            const prefix = item.scope === "shared" ? "/admin" : "";
            await api.del(`${prefix}/ai/connections/${item.provider}`, item.version);
            await Promise.all([loadConnections(), loadModels()]);
          } catch (error) {
            notify(error.message);
          }
        });
        row.append(remove);
      }
      list.append(row);
    });
}

$("#connection-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (form.getAttribute("aria-busy") === "true") return;
  const submit = form.querySelector('[type="submit"]');
  form.setAttribute("aria-busy", "true");
  submit.disabled = true;
  submit.textContent = "Đang lưu…";
  const provider = $("#connection-provider").value;
  const userId = state.user?.id;
  const scope = $("#connection-scope").value;
  const current = state.connections.find(
    (item) => item.provider === provider && item.scope === scope,
  );
  try {
    const saved = await api.put(
      `${scope === "shared" ? "/admin" : ""}/ai/connections/${provider}`,
      {
        apiKey: $("#connection-key").value.trim(),
        expectedVersion: current?.version || 0,
        enabled: true,
      },
    );
    if (state.user?.id !== userId) return;
    connectionsRevision++;
    const index = state.connections.findIndex(
      (item) => item.provider === provider && item.scope === scope,
    );
    if (index < 0) state.connections.push(saved);
    else state.connections[index] = saved;
    renderConnectionSummary();
    $("#connection-key").value = "";
    await Promise.all([loadConnections(), loadModels({ prefer: provider })]);
    notify("Đã lưu khóa. Kiểm tra model khả dụng trong menu Model.");
  } catch (error) {
    notify(error.message);
  } finally {
    form.removeAttribute("aria-busy");
    submit.disabled = false;
    submit.textContent = "Lưu khóa";
  }
});
$("#connection-scope").addEventListener("change", () => {
  $("#connection-key").placeholder =
    $("#connection-scope").value === "shared" ? "Khóa API dùng chung" : "Khóa API cá nhân";
});

async function chatgptAction(action) {
  connectionsRevision++;
  const userId = state.user?.id;
  const buttons = ["#chatgpt-start", "#chatgpt-finish", "#chatgpt-disconnect"];
  buttons.forEach((selector) => {
    $(selector).disabled = true;
  });
  try {
    const result =
      action === "disconnect"
        ? await api.del("/ai/chatgpt")
        : await api.post(`/ai/chatgpt/${action}`, {});
    if (state.user?.id !== userId) return;
    if (action === "start") {
      const url = new URL(result.url);
      if (
        url.protocol !== "https:" ||
        url.hostname !== "auth.openai.com" ||
        url.username ||
        url.password
      )
        throw new Error("Địa chỉ đăng nhập OpenAI không hợp lệ.");
      state.chatgpt = {
        available: true,
        pending: true,
        connected: false,
        url: url.href,
        instructions: result.instructions,
      };
    } else if (action === "finish") {
      if (result.connected) {
        state.chatgpt = { available: true, pending: false, connected: true };
        renderChatgpt();
        await loadModels({ prefer: "chatgpt" });
        notify("Đã kết nối ChatGPT. Kiểm tra model khả dụng trong menu Model.");
      } else {
        notify("Chưa hoàn tất đăng nhập. Hãy hoàn tất trên trang OpenAI rồi xác nhận lại.");
      }
    } else {
      state.chatgpt = { available: true, pending: false, connected: false };
      state.models.groups = state.models.groups.filter((group) => group.id !== "chatgpt");
      renderChatgpt();
      await loadModels();
    }
    renderChatgpt();
  } catch (error) {
    notify(error.message);
  } finally {
    buttons.forEach((selector) => {
      $(selector).disabled = false;
    });
  }
}
$("#chatgpt-start").addEventListener("click", () => chatgptAction("start"));
$("#chatgpt-finish").addEventListener("click", () => chatgptAction("finish"));
$("#chatgpt-disconnect").addEventListener("click", () => chatgptAction("disconnect"));

export { loadConnections, renderChatgpt };
