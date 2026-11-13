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

// Render the answer: headings, bullet lines and **bold** from Markdown, and "[1]" markers as
// buttons that open the cited evidence. Everything goes through textContent, never innerHTML.
function appendInline(parent, text, data) {
  text.split(/(\[\d+\]|\*\*[^*]+\*\*)/).forEach((part) => {
    if (!part) return;
    const cite = part.match(/^\[(\d+)\]$/);
    const citation = cite && data.citations?.[Number(cite[1]) - 1];
    if (citation) {
      const button = element("button", "cite", part);
      button.addEventListener("click", () => openEvidence(citation));
      parent.append(button);
    } else if (/^\*\*[^*]+\*\*$/.test(part)) {
      parent.append(element("strong", "", part.slice(2, -2)));
    } else {
      parent.append(part);
    }
  });
}

function answerNode(data) {
  const box = element("div", "answer-text");
  (data.answer || "").split("\n").forEach((raw) => {
    const line = raw.trim();
    if (!line || /^[-*_]{3,}$/.test(line)) return;
    const heading = line.match(/^#{1,6}\s+(.*)$/);
    const bullet = line.match(/^[-*•]\s+(.*)$/);
    const paragraph = element("p", heading ? "answer-heading" : bullet ? "answer-bullet" : "");
    appendInline(paragraph, heading ? heading[1] : bullet ? "• " + bullet[1] : line, data);
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
  renderComposerError();
  $("#send-question").disabled = Boolean(state.pendingChat) || !$("#question").value.trim();
  renderCounts();
}

// The last turns of this conversation, so a follow-up ("tất cả các loại luôn") has its context.
function historyFor(chat) {
  return (chat?.messages || [])
    .filter((message) => message.role === "user" || message.data)
    .slice(-6)
    .map((message) => ({
      role: message.role,
      text: String((message.role === "user" ? message.text : message.data.answer) || "").slice(0, 3000),
    }))
    .filter((turn) => turn.text.trim());
}

function requestBody(question, selection) {
  const body = {
    question,
    ...selection,
    history: historyFor(activeChat()),
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
    live: { stage: "", sources: [], text: "", citations: [] },
  };
  state.pendingChat = pending;
  state.chatError = null;
  active.messages.push({ role: "user", text: question });
  $("#question").value = "";
  fitQuestion();
  $("#query-public-confirm").checked = false;
  persist();
  renderChat();
  scrollToLatest();
  const timer = setInterval(renderProgress, 1000);
  let frame = 0;
  const isCurrent = () =>
    state.user?.id === userId &&
    state.pendingChat === pending &&
    state.chats.some((chat) => chat.id === chatId);
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
      (event) => {
        if (!isCurrent()) return;
        trackLive(pending, event);
        if (event.type !== "text") return renderProgress();
        // Từng đoạn chữ đến rất nhanh: gộp lại, mỗi khung hình vẽ một lần.
        if (!frame)
          frame = requestAnimationFrame(() => {
            frame = 0;
            if (!isCurrent()) return;
            renderProgress();
            if (state.chatId === chatId) scrollToLatest();
          });
      },
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
    state.chatError = { userId, chatId, question, message: error.message };
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

// Lỗi yêu cầu trong thanh nhập
function renderComposerError() {
  const error = state.chatError;
  const visible = error && error.userId === state.user?.id && error.chatId === state.chatId;
  $("#chat-error").hidden = !visible;
  $("#chat-error-message").textContent = visible ? error.message : "";
}

// Khôi phục bản nháp để người dùng kiểm tra trước khi gửi lại
$("#restore-question").addEventListener("click", () => {
  const error = state.chatError;
  if (!error || error.userId !== state.user?.id || error.chatId !== state.chatId) return;
  $("#question").value = error.question;
  $("#question").dispatchEvent(new Event("input"));
  $("#question").focus();
  state.chatError = null;
  renderComposerError();
});

const STAGE_TITLE = {
  retrieving: "Đang tìm nguồn trong kho",
  web: "Đang tra cứu nguồn web",
  drafting: "Đang soạn câu trả lời",
  cached: "Đang kiểm tra lại nguồn của câu trả lời đã lưu",
};
const STAGE_LOG = {
  retrieving: "Đang tìm nguồn trong kho…",
  web: "Đang tra cứu nguồn web…",
  drafting: "Đang soạn câu trả lời…",
  cached: "Câu hỏi này đã được trả lời; đang kiểm tra nguồn còn hiệu lực.",
};

function elapsed(pending) {
  return `${((Date.now() - pending.startedAt) / 1000).toFixed(1)} giây`;
}

// Ghi nhận các sự kiện của luồng trả lời để hiện nguồn và từng ý ngay khi máy chủ gửi.
function trackLive(pending, event) {
  const live = pending.live;
  if (event.type === "stage") {
    live.stage = event.stage;
    // Nhóm kho mới bắt đầu: bỏ nội dung của nhóm trước.
    if (event.stage === "retrieving") Object.assign(live, { sources: [], text: "", citations: [] });
    pending.logs.push(`${STAGE_LOG[event.stage] || event.stage} (${elapsed(pending)})`);
  } else if (event.type === "sources") {
    live.sources = event.items || [];
    pending.logs.push(`Tìm thấy ${live.sources.length} nguồn (${elapsed(pending)}).`);
  } else if (event.type === "text" || event.type === "claim") {
    // "claim" là một dòng hoàn chỉnh của máy chủ cũ; "text" là từng đoạn khi model đang viết.
    if (!live.text) pending.logs.push(`Bắt đầu viết câu trả lời (${elapsed(pending)}).`);
    live.text += event.type === "claim" && live.text ? "\n" + event.text : event.text;
    live.citations.push(...(event.citations || []));
  } else if (event.type === "reset") {
    Object.assign(live, { text: "", citations: [] });
    pending.logs.push("Đang soạn lại câu trả lời.");
  }
}

function renderLive(pending) {
  const box = $("#progress-live");
  const { sources, text, citations } = pending.live;
  const parts = [];
  if (sources.length) {
    const list = element("ul", "live-sources");
    sources.forEach((source) => {
      const place = [source.article, source.clause].filter(Boolean).join(" · ");
      list.append(element("li", "", `${source.title}${place ? " · " + place : ""}`));
    });
    parts.push(element("strong", "", "Nguồn đang xem xét"), list);
  }
  if (text) {
    parts.push(
      element("strong", "", "Câu trả lời đang hình thành"),
      answerNode({ answer: text, citations }),
    );
  }
  box.replaceChildren(...parts);
  box.hidden = !parts.length;
}

// Tiến trình chỉ hiển thị các bước mà trình duyệt thực sự biết
function renderProgress() {
  const pending = state.pendingChat;
  $("#chat-progress").hidden = !pending || state.chatId !== pending.chatId;
  $("#send-question").disabled = Boolean(pending) || !$("#question").value.trim();
  if (!pending || state.chatId !== pending.chatId) return;
  $("#progress-title").textContent = STAGE_TITLE[pending.live.stage] || "Đang xử lý câu hỏi";
  $("#progress-detail").textContent =
    `${Math.floor((Date.now() - pending.startedAt) / 1000)} giây · Câu trả lời hiện dần khi được viết; bản cuối cùng sẽ thay thế bản nháp này.`;
  $("#progress-log").replaceChildren(...pending.logs.map((text) => element("li", "", text)));
  renderLive(pending);
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

// Grow the composer with its text, up to the CSS max-height.
function fitQuestion() {
  const box = $("#question");
  box.style.height = "auto";
  box.style.height = `${box.scrollHeight}px`;
}

// Enter in the date or model-filter fields must not submit the question.
$("#question-form").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && event.target.matches("input")) event.preventDefault();
});
$("#question").addEventListener("input", () => {
  fitQuestion();
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
  fitQuestion();
  $("#send-question").disabled = false;
  $("#question").focus();
});
document.addEventListener("chat-selected", () => {
  $("#question").value = "";
  fitQuestion();
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
