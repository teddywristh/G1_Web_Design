import { api } from "./api.js";
import { setAuthMode, showAuth } from "./auth.js";
import {
  $,
  SOURCE_TEXT,
  STATUS_TEXT,
  element,
  limitText,
  notify,
  persist,
  renderCounts,
  state,
} from "./core.js";
import { openEvidence } from "./evidence.js";
import { navigate } from "./navigation.js";
import { renderChatgpt, syncAiControls } from "./settings.js";

// Câu hỏi, câu trả lời và lịch sử hội thoại
function activeChat() {
  return state.chats.find((chat) => chat.id === state.chatId);
}

function newChat() {
  state.chatId = null;
  $("#query-public-confirm").checked = false;
  $("#question-form").reset();
  renderChat();
  navigate("chat");
  $("#question").focus();
}

// Turn "[1]" markers in an answer into buttons that open the cited evidence.
function answerNode(data) {
  const box = element("div", "answer-text");
  (data.answer || "").split("\n").forEach((line) => {
    const paragraph = element("p");
    line.split(/(\[\d+\])/).forEach((part) => {
      const match = part.match(/^\[(\d+)\]$/);
      const citation = match && data.citations?.[Number(match[1]) - 1];
      if (!citation) {
        paragraph.append(part);
        return;
      }
      const button = element("button", "cite", part);
      button.addEventListener("click", () => openEvidence(citation));
      paragraph.append(button);
    });
    box.append(paragraph);
  });
  return box;
}

function listBlock(title, items) {
  const block = element("div", "answer-block");
  block.append(element("strong", "", title));
  const list = element("ul");
  items.forEach((item) => list.append(element("li", "", item)));
  block.append(list);
  return block;
}

function assistantBubble(message) {
  const bubble = element("div", "answer-message");
  bubble.append(element("span", "", "Legal AI"));
  const data = message.data;
  if (!data) {
    bubble.append(element("p", "", message.text));
    return bubble;
  }
  const head = element("div", "answer-head");
  head.append(
    element(
      "span",
      `status-badge ${data.status === "answered" ? "ready" : "uploaded"}`,
      STATUS_TEXT[data.status] || data.status,
    ),
  );
  if (data.as_of)
    head.append(
      element("small", "", `Mốc thời gian: ${new Date(data.as_of).toLocaleDateString("vi-VN")}`),
    );
  if (data.provider) {
    const source =
      { chatgpt: "ChatGPT cá nhân", personal: "Key cá nhân", shared: "Key dùng chung" }[
        data.credential_source
      ] ||
      data.credential_source ||
      "";
    head.append(element("small", "", `${data.provider} · ${source}`));
  }
  bubble.append(head, answerNode(data));
  if (data.missing_facts?.length) bubble.append(listBlock("Cần bổ sung", data.missing_facts));
  if (data.assumptions?.length) bubble.append(listBlock("Giả định", data.assumptions));
  if (data.citations?.length) {
    const block = element("div", "answer-block");
    block.append(element("strong", "", "Nguồn"));
    data.citations.forEach((citation, index) => {
      const button = element("button", "citation-row");
      const place = [citation.article, citation.clause].filter(Boolean).join(" · ");
      button.append(
        element(
          "span",
          "",
          `[${index + 1}] ${citation.document_title}${place ? " · " + place : ""}`,
        ),
        element("small", "", SOURCE_TEXT[citation.source_type] || ""),
      );
      button.addEventListener("click", () => openEvidence(citation));
      block.append(button);
    });
    bubble.append(block);
  }
  if (data.source_limitations?.length) {
    const notes = element("div", "limit-chips");
    data.source_limitations.forEach((code) => notes.append(element("span", "", limitText(code))));
    bubble.append(notes);
  }
  return bubble;
}

function renderChat() {
  const active = activeChat();
  const hasMessages = Boolean(active?.messages.length);
  $("#history-bar").hidden = state.chats.length === 0;
  $("#history-select").replaceChildren(new Option("Chọn cuộc trò chuyện", ""));
  state.chats.forEach((chat) =>
    $("#history-select").add(new Option(chat.title || "Chưa đặt tên", chat.id)),
  );
  $("#history-select").value = active?.id || "";
  $("#delete-chat").hidden = !active;
  $("#welcome").hidden = hasMessages;
  $("#suggestions").hidden = hasMessages;
  $("#conversation").hidden = !hasMessages;
  $("#chat-title").value = active?.title || "";
  $("#messages").replaceChildren();
  active?.messages.forEach((message) => {
    if (message.role === "assistant") {
      $("#messages").append(assistantBubble(message));
      return;
    }
    const bubble = element("div", "question-message");
    bubble.append(element("span", "", "Bạn"), element("p", "", message.text));
    $("#messages").append(bubble);
  });
  $("#messages").scrollTop = $("#messages").scrollHeight;
  $("#send-question").disabled = !$("#question").value.trim();
  renderCounts();
}

function requestBody(question) {
  const provider = $("#provider").value;
  const body = {
    question,
    provider,
    credential_source: $("#credential-source").value,
    engine: $("#engine").value,
    knowledge_base_ids: [...state.selected],
    retrieval_mode: $("#retrieval-mode").value,
    web_mode: $("#web-search").checked ? "official" : "off",
    public_embedding_input_confirmed: $("#query-public-confirm").checked,
  };
  if ($("#as-of").value) body.as_of = $("#as-of").value;
  if ($("#model").value.trim()) body.model = $("#model").value.trim();
  return body;
}

$("#question-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = $("#question").value.trim();
  if (!question) return;
  if (!state.user) {
    setAuthMode("login");
    showAuth("Đăng nhập để đặt câu hỏi và kết nối AI.");
    return;
  }
  const hasReadyKb = state.kbs.some((kb) => kb.ready && state.selected.has(kb.id));
  if (
    hasReadyKb &&
    state.aiOptions?.embedding?.requiresPublicInput &&
    $("#retrieval-mode").value === "hybrid" &&
    !$("#query-public-confirm").checked
  ) {
    notify("Xác nhận câu hỏi không chứa dữ liệu cá nhân hoặc thông tin mật.");
    return;
  }
  if (
    ["anthropic", "deepseek", "openrouter"].includes($("#provider").value) &&
    !$("#model").value.trim()
  ) {
    notify("Nhập ID model của nhà cung cấp đã chọn.");
    return;
  }
  let active = activeChat();
  if (!active) {
    active = {
      id: crypto.randomUUID(),
      title: question.slice(0, 70),
      date: new Date().toISOString(),
      messages: [],
    };
    state.chats.unshift(active);
    state.chatId = active.id;
  }
  active.messages.push({ role: "user", text: question });
  $("#question-form").reset();
  $("#send-question").disabled = true;
  persist();
  renderChat();
  const chatId = active.id;
  $("#assistant-status").textContent = "Đang tra cứu nguồn và soạn câu trả lời…";
  let reply;
  try {
    const body = requestBody(question);
    $("#query-public-confirm").checked = false;
    const data = await api.post("/rag/ask", body);
    reply = { role: "assistant", text: data.answer, data: slimResponse(data) };
  } catch (error) {
    if (error.code === "chatgpt_disconnected") {
      state.chatgpt = { ...state.chatgpt, connected: false, pending: false };
      renderChatgpt();
    }
    reply = { role: "assistant", text: error.message };
  }
  $("#assistant-status").textContent =
    "Lịch sử hội thoại chỉ lưu trên thiết bị này và bị xóa khi đăng xuất. Câu trả lời không thay thế tư vấn pháp lý.";
  const chat = state.chats.find((item) => item.id === chatId);
  if (!chat) return;
  chat.messages.push(reply);
  persist();
  if (state.chatId === chatId) renderChat();
});

// Keep only what the view needs; retrieved_chunks stay out of the history.
function slimResponse(data) {
  return {
    status: data.status,
    answer: data.answer,
    as_of: data.as_of,
    citations: data.citations,
    assumptions: data.assumptions,
    missing_facts: data.missing_facts,
    source_limitations: data.source_limitations,
    provider: data.provider,
    credential_source: data.credential_source,
  };
}

$("#question").addEventListener("input", () => {
  $("#query-public-confirm").checked = false;
  $("#send-question").disabled = !$("#question").value.trim();
});
$("#question").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    $("#question-form").requestSubmit();
  }
});
$("#suggestions").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  $("#query-public-confirm").checked = false;
  $("#question").value = button.textContent;
  $("#send-question").disabled = false;
  $("#question").focus();
});
$("#history-select").addEventListener("change", (event) => {
  state.chatId = event.target.value || null;
  $("#question-form").reset();
  renderChat();
});
$("#chat-title").addEventListener("input", (event) => {
  const active = activeChat();
  if (!active) return;
  active.title = event.target.value;
  persist();
  $("#history-select").selectedOptions[0].textContent = active.title || "Chưa đặt tên";
});
$("#delete-chat").addEventListener("click", () => {
  state.chats = state.chats.filter((chat) => chat.id !== state.chatId);
  persist();
  newChat();
});
$("#provider").addEventListener("change", () => {
  const provider = $("#provider").value;
  $("#model").value = "";
  if (["deepseek", "openrouter"].includes(provider)) {
    $("#engine").value = "opencode";
    $("#retrieval-mode").value = "keyword";
  }
  if (provider === "anthropic") $("#engine").value = "direct";
  if (provider !== "openai" && $("#credential-source").value === "chatgpt")
    $("#credential-source").value = "auto";
  syncAiControls();
  persist();
});
$("#engine").addEventListener("change", () => {
  if ($("#engine").value === "direct" && $("#credential-source").value === "chatgpt")
    $("#credential-source").value = "auto";
  if ($("#engine").value === "opencode") $("#retrieval-mode").value = "keyword";
  syncAiControls();
  persist();
});
$("#credential-source").addEventListener("change", () => {
  if ($("#credential-source").value === "chatgpt") $("#retrieval-mode").value = "keyword";
  syncAiControls();
  renderChatgpt();
  persist();
});
$("#retrieval-mode").addEventListener("change", () => {
  syncAiControls();
  persist();
});
$("#model").addEventListener("change", persist);

export { newChat, renderChat };
