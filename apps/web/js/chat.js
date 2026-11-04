import { askSources } from "./requests.js";
import { renderHistory, removeChat } from "./history.js";
import { closeEvidence } from "./evidence.js";
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
import { focusPicker, loadModels, selectedModel } from "./models.js";
import { renderChatgpt } from "./settings.js";

// Câu hỏi, câu trả lời và lịch sử hội thoại
function activeChat() {
  return state.chats.find((chat) => chat.id === state.chatId);
}

function newChat() {
  closeEvidence(false);
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
  if (data.activity?.length) {
    const activity = element("details", "answer-activity");
    activity.append(element("summary", "", `Hoạt động tra cứu · ${data.duration || 0} giây`));
    const list = element("ol");
    data.activity.forEach((text) => list.append(element("li", "", text)));
    activity.append(list);
    bubble.append(activity);
  }
  if (data.missing_facts?.length) bubble.append(listBlock("Cần bổ sung", data.missing_facts));
  if (data.assumptions?.length) bubble.append(listBlock("Giả định", data.assumptions));
  if (data.citations?.length) {
    const block = element("details", "answer-sources");
    block.append(element("summary", "", `Nguồn tham khảo · ${data.citations.length}`));
    const sources = element("div", "source-list");
    data.citations.forEach((citation, index) => {
      const button = element("button", "citation-row");
      const place = [citation.article, citation.clause].filter(Boolean).join(" · ");
      button.append(
        element(
          "span",
          "",
          `[${index + 1}] ${citation.document_title}${place ? " · " + place : ""}`,
        ),
        element(
          "small",
          "",
          `${citation.provision_version_id ? "PDF trong kho" : "Nguồn web"}${SOURCE_TEXT[citation.source_type] ? " · " + SOURCE_TEXT[citation.source_type] : ""}${citation.page_number ? " · trang " + citation.page_number : ""}`,
        ),
      );
      button.addEventListener("click", () => openEvidence(citation));
      sources.append(button);
    });
    block.append(sources);
    bubble.append(block);
  }
  if (data.scope_errors?.length)
    bubble.append(listBlock("Một số kho chưa tra cứu được", data.scope_errors));
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
  renderHistory();
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
  renderProgress();
  $("#send-question").disabled = Boolean(state.pendingChat) || !$("#question").value.trim();
  renderCounts();
}

function requestBody(question, selection) {
  const body = {
    question,
    ...selection,
    web_mode: $("#web-search").checked ? "official" : "off",
    public_embedding_input_confirmed: $("#query-public-confirm").checked,
  };
  if ($("#as-of").value) body.as_of = $("#as-of").value;
  return body;
}

$("#question-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = $("#question").value.trim();
  if (!question || state.pendingChat) return;
  if (!state.user) {
    setAuthMode("login");
    showAuth("Đăng nhập để đặt câu hỏi và kết nối AI.");
    return;
  }
  const selection = selectedModel();
  if (!selection) {
    notify("Chọn model AI trước khi gửi câu hỏi.");
    focusPicker();
    return;
  }
  const hasReadyKb = state.kbs.some((kb) => kb.ready);
  if (
    hasReadyKb &&
    state.aiOptions?.embedding?.requiresPublicInput &&
    !$("#query-public-confirm").checked
  ) {
    notify("Xác nhận câu hỏi không chứa dữ liệu cá nhân hoặc thông tin mật.");
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
  const body = requestBody(question, selection);
  const knowledgeBases = [...state.kbs];
  const userId = state.user.id;
  const chatId = active.id;
  const pending = {
    chatId,
    userId,
    startedAt: Date.now(),
    logs: ["Đã tiếp nhận câu hỏi."],
  };
  state.pendingChat = pending;
  active.messages.push({ role: "user", text: question });
  $("#question").value = "";
  $("#query-public-confirm").checked = false;
  persist();
  renderChat();
  scrollToLatest();
  const timer = setInterval(renderProgress, 1000);
  const isCurrent = () => state.user?.id === userId && state.pendingChat === pending && state.chats.some(chat => chat.id === chatId);
  let reply;
  try {
    const data = await askSources(
      body,
      knowledgeBases,
      (text) => {
        if (!isCurrent()) return;
        pending.logs.push(text);
        renderProgress();
      },
      isCurrent,
    );
    if (!data || !isCurrent()) return;
    reply = {
      role: "assistant",
      text: data.answer,
      data: {
        ...slimResponse(data),
        activity: [...pending.logs],
        duration: Math.round((Date.now() - pending.startedAt) / 1000),
      },
    };
  } catch (error) {
    if (!isCurrent()) return;
    if (error.code === "chatgpt_disconnected") {
      state.chatgpt = { ...state.chatgpt, connected: false, pending: false };
      renderChatgpt();
      loadModels();
    }
    reply = { role: "assistant", text: error.message };
  } finally {
    clearInterval(timer);
    if (state.pendingChat === pending) state.pendingChat = null;
    renderProgress();
  }
  if (state.user?.id !== userId) return;
  const chat = state.chats.find((item) => item.id === chatId);
  if (!chat) return;
  chat.messages.push(reply);
  persist();
  renderHistory();
  if (state.chatId === chatId) {
    renderChat();
    scrollToLatest();
  }
});

// Tiến trình chỉ hiển thị các bước mà trình duyệt thực sự biết
function renderProgress() {
  const pending = state.pendingChat;
  $("#chat-progress").hidden = !pending || state.chatId !== pending.chatId;
  $("#send-question").disabled = Boolean(pending) || !$("#question").value.trim();
  if (!pending || state.chatId !== pending.chatId) return;
  $("#progress-title").textContent = "Đang xử lý câu hỏi";
  $("#progress-detail").textContent =
    `${Math.floor((Date.now() - pending.startedAt) / 1000)} giây · Máy chủ sẽ gửi câu trả lời khi xử lý xong.`;
  $("#progress-log").replaceChildren(...pending.logs.map((text) => element("li", "", text)));
}

function scrollToLatest() {
  const container = $("#chat-scroll");
  container.scrollTop = container.scrollHeight;
}

// Chỉ lưu dữ liệu cần để mở lại hội thoại
function slimResponse(data) {
  return {
    status: data.status,
    answer: data.answer,
    as_of: data.as_of,
    citations: data.citations,
    assumptions: data.assumptions,
    missing_facts: data.missing_facts,
    source_limitations: data.source_limitations,
    scope_errors: data.scope_errors,
    provider: data.provider,
    credential_source: data.credential_source,
  };
}

$("#question").addEventListener("input", () => {
  $("#query-public-confirm").checked = false;
  $("#send-question").disabled = Boolean(state.pendingChat) || !$("#question").value.trim();
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
document.addEventListener("chat-selected", () => {
  $("#question").value = "";
  renderChat();
  scrollToLatest();
});
$("#chat-title").addEventListener("input", (event) => {
  const active = activeChat();
  if (!active) return;
  active.title = event.target.value;
  persist();
  renderHistory();
});
$("#delete-chat").addEventListener("click", () => {
  removeChat(state.chatId);
});
export { newChat, renderChat };
