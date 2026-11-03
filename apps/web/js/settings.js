import { api } from "./api.js";
import { $, element, isAdmin, notify, persist, state } from "./core.js";

// Khóa API và kết nối AI
function syncAiControls() {
  const provider = $("#provider").value;
  const engine = $("#engine").value;
  const source = $("#credential-source").value;
  const available = Boolean(state.aiOptions?.engines?.opencode);
  $("#engine option[value=opencode]").disabled = !available || provider === "anthropic";
  $("#engine option[value=direct]").disabled = false;
  const chatgptOption = $("#credential-source option[value=chatgpt]");
  chatgptOption.hidden = provider !== "openai" || engine !== "opencode" || !state.chatgpt.available;
  chatgptOption.disabled = !state.chatgpt.connected;
  $("#retrieval-mode option[value=hybrid]").disabled =
    source === "chatgpt" && !["openrouter", "local"].includes(state.aiOptions?.embedding?.provider);
  $("#query-public-label").hidden = !(
    state.aiOptions?.embedding?.requiresPublicInput && $("#retrieval-mode").value === "hybrid"
  );
  $("#model").placeholder = provider === "openai" ? "Để trống dùng mặc định" : "Nhập ID model";
}

function selectChatgpt() {
  $("#provider").value = "openai";
  $("#engine").value = "opencode";
  $("#credential-source").value = "chatgpt";
  $("#retrieval-mode").value = ["local", "openrouter"].includes(state.aiOptions?.embedding?.provider) ? "hybrid" : "keyword";
  $("#model").value = "gpt-5.6-luna";
  syncAiControls();
  persist();
  renderChatgpt();
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
  $("#chatgpt-use").hidden = !connection.connected || $("#credential-source").value === "chatgpt";
  $("#chatgpt-disconnect").hidden = !connection.connected && !connection.pending;
  syncAiControls();
}

async function loadConnections({ restore = false } = {}) {
  if (!state.user) return;
  const userId = state.user.id;
  try {
    const options = await api.get("/ai/connections");
    if (state.user?.id !== userId) return;
    state.aiOptions = options;
    state.connections = options.connections;
    const available = Boolean(
      options.methods?.find((item) => item.id === "chatgpt_oauth")?.available,
    );
    if (available) {
      const status = await api.get("/ai/chatgpt");
      if (state.user?.id !== userId) return;
      state.chatgpt = { ...state.chatgpt, ...status, available };
      if (restore && status.connected) selectChatgpt();
    } else {
      state.chatgpt = { available: false, connected: false, pending: false };
    }
  } catch (error) {
    notify(error.message);
    return;
  }
  const list = $("#connection-list");
  list.replaceChildren();
  renderChatgpt();
  const embedding = state.aiOptions?.embedding;
  $("#embedding-info").textContent =
    embedding?.provider === "local"
      ? `Embedding chạy trên GPU local (${embedding.model}); không cần khóa OpenRouter.`
      : embedding?.provider === "openrouter"
        ? `Embedding dùng OpenRouter (${embedding.model || "chưa chọn model"}) với key chung do hệ thống cấu hình${embedding.configured ? "." : "; chưa cấu hình đầy đủ."}`
        : "Embedding dùng khóa OpenAI; nếu không có khóa OpenAI, hãy dùng mục tìm theo số hiệu/điều.";
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
      row.append(element("span", "", `${names[item.provider]} · ${scope}: `));
      row.append(
        element(
          "strong",
          "",
          item.configured ? (item.enabled ? "đã cấu hình" : "đang tắt") : "chưa có",
        ),
      );
      if ((item.scope === "personal" || isAdmin()) && item.origin === "stored" && item.configured) {
        const remove = element("button", "text-button danger", "Xóa");
        remove.addEventListener("click", async () => {
          try {
            const prefix = item.scope === "shared" ? "/admin" : "";
            await api.del(`${prefix}/ai/connections/${item.provider}`, item.version);
            loadConnections();
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
  const provider = $("#connection-provider").value;
  const scope = $("#connection-scope").value;
  const current = state.connections.find(
    (item) => item.provider === provider && item.scope === scope,
  );
  try {
    await api.put(`${scope === "shared" ? "/admin" : ""}/ai/connections/${provider}`, {
      apiKey: $("#connection-key").value.trim(),
      expectedVersion: current?.version || 0,
      enabled: true,
    });
    notify("Đã lưu khóa. Khóa không được hiển thị lại.");
    loadConnections();
  } catch (error) {
    notify(error.message);
  } finally {
    $("#connection-key").value = "";
  }
});
$("#connection-scope").addEventListener("change", () => {
  $("#connection-key").placeholder =
    $("#connection-scope").value === "shared" ? "Khóa API dùng chung" : "Khóa API cá nhân";
});

async function chatgptAction(action) {
  const userId = state.user?.id;
  const buttons = ["#chatgpt-start", "#chatgpt-finish", "#chatgpt-use", "#chatgpt-disconnect"];
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
      state.chatgpt = { available: true, pending: false, connected: Boolean(result.connected) };
      if (result.connected) {
        selectChatgpt();
        notify("Đã kết nối ChatGPT cho phiên của bạn.");
      }
    } else {
      state.chatgpt = { available: true, pending: false, connected: false };
      if ($("#credential-source").value === "chatgpt") {
        $("#credential-source").value = "auto";
        persist();
      }
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
$("#chatgpt-use").addEventListener("click", selectChatgpt);
$("#chatgpt-disconnect").addEventListener("click", () => chatgptAction("disconnect"));

export { loadConnections, renderChatgpt, syncAiControls };
