import { api } from "./api.js";
import { $, element, notify, persist, state } from "./core.js";
import { navigate } from "./navigation.js";

// Một combobox duy nhất chọn nhà cung cấp + model từ các kết nối đã cấu hình
const SOURCE_TEXT = {
  personal: "key cá nhân",
  shared: "key dùng chung",
  chatgpt: "tài khoản ChatGPT",
};
const GROUP_ERROR_TEXT = {
  ai_authentication_failed: "Nhà cung cấp từ chối khóa; kiểm tra lại trong Thiết lập.",
  ai_rate_limited: "Nhà cung cấp đang giới hạn lượt; gõ ID model để dùng tạm.",
  chatgpt_disconnected: "Phiên ChatGPT đã hết hạn; kết nối lại trong Thiết lập.",
};
// Same shape the backend accepts for a model ID.
const MODEL_ID = /^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$/;
const PREFERRED = { chatgpt: "gpt-5.6-luna" };
const PAGE = 60;
const RECONNECT_ERRORS = new Set(["ai_authentication_failed", "chatgpt_disconnected"]);
const PROVIDERS = [
  { id: "openai", label: "OpenAI" },
  { id: "anthropic", label: "Claude (Anthropic)" },
  { id: "deepseek", label: "DeepSeek" },
  { id: "openrouter", label: "OpenRouter" },
  { id: "chatgpt", label: "Tài khoản ChatGPT" },
];
let entries = [];
let active = -1;
let modelsRevision = 0;

function groupOf(id) {
  return state.models.groups.find((group) => group.id === id);
}

function choiceLabel(choice) {
  const group = choice && groupOf(choice.group);
  if (!group) return "";
  const model = group.models.find((item) => item.id === choice.model);
  return `${group.label} · ${model?.name || choice.model}`;
}

function defaultChoice(prefer) {
  const groups = state.models.groups.filter(
    (group) => group.models.length && !RECONNECT_ERRORS.has(group.error),
  );
  const group = groups.find((item) => item.id === prefer) || groups[0];
  if (!group) return null;
  const preferred = group.models.find((model) => model.id === PREFERRED[group.id]);
  return { group: group.id, model: (preferred || group.models[0]).id };
}

function selectedGroup() {
  return groupOf(state.ai?.group);
}

function isOpen() {
  return !$("#model-popover").hidden;
}

function renderPicker() {
  const label = $("#model-label");
  const group = selectedGroup();
  const model = group?.models.find((item) => item.id === state.ai.model);
  label.textContent =
    state.models.loading && !group ? "Đang tải…" : group ? model?.name || state.ai.model : "Model";
  $("#model-button").title = group ? choiceLabel(state.ai) : "Chọn nhà cung cấp và model";
}

function matches(text, terms) {
  const value = text.toLowerCase();
  return terms.every((term) => value.includes(term));
}

function optionNode(entry, index) {
  const selected = state.ai?.group === entry.group.id && state.ai?.model === entry.model;
  const node = element("li", "combobox-option");
  node.id = `model-option-${index}`;
  node.setAttribute("role", "option");
  node.setAttribute("aria-selected", String(selected));
  node.append(element("span", "", entry.name));
  if (entry.custom) node.append(element("small", "", "ID tự nhập"));
  else if (entry.name !== entry.model) node.append(element("small", "", entry.model));
  node.addEventListener("click", () => choose(entry));
  return node;
}

// Hiện các nhà cung cấp và hướng dẫn kết nối khi chưa có model.
function renderProviders() {
  const list = $("#model-providers");
  list.replaceChildren();
  $("#model-panel").hidden = true;
  list.hidden = false;
  if (state.models.error) {
    list.append(element("p", "combobox-note", state.models.error));
  } else if (!state.models.apiKeysAvailable && state.user && !state.models.loading) {
    list.append(
      element(
        "p",
        "combobox-note",
        "Máy chủ chưa bật model qua API key. Liên hệ quản trị viên để bật kết nối này.",
      ),
    );
  }
  PROVIDERS.forEach((provider) => {
    const group = groupOf(provider.id);
    const reconnect = group && RECONNECT_ERRORS.has(group.error);
    const usable = group && !reconnect;
    const connected = provider.id === "chatgpt" && state.chatgpt.connected;
    const status = group
      ? reconnect
        ? "Cần kết nối lại"
        : group.error
          ? "Lỗi tải model"
          : `Đã kết nối · ${SOURCE_TEXT[group.source] || group.source}`
      : connected
        ? state.models.loading
          ? "Đã kết nối · Đang tải model…"
          : "Đã kết nối · Chưa tải được model"
        : state.models.loading
          ? "Đang kiểm tra…"
          : state.models.error
            ? "Chưa kiểm tra được kết nối"
            : "Chưa kết nối";
    const button = element("button", "model-provider");
    button.type = "button";
    button.setAttribute("role", "menuitem");
    button.disabled = state.models.loading && !group;
    if (state.ai?.group === provider.id) button.classList.add("is-current");
    const text = element("span");
    text.append(
      element("strong", "", group?.label || provider.label),
      element("small", "", status),
    );
    button.append(
      text,
      element(
        "span",
        "model-provider-action",
        usable ? "Chọn model ›" : connected ? "Tải lại" : state.user ? "Thiết lập" : "Đăng nhập",
      ),
    );
    button.addEventListener("click", () => {
      if (usable) {
        showGroup(group);
        return;
      }
      if (connected) {
        loadModels({ prefer: "chatgpt" });
        return;
      }
      close();
      navigate("settings", "ai");
      if (state.user && provider.id !== "chatgpt") {
        $("#connection-provider").value = provider.id;
        $("#connection-key").focus();
      }
    });
    list.append(button);
  });
}

let currentGroup = null;

// Step 2: the models of one connection, filterable, with a typed-ID fallback.
function showGroup(group) {
  currentGroup = group;
  $("#model-providers").hidden = true;
  $("#model-panel").hidden = false;
  $("#model-provider-name").textContent = group.label;
  $("#model-filter").value = "";
  renderOptions();
  setActive(
    entries.findIndex((entry) => entry.model === state.ai?.model && state.ai?.group === group.id),
  );
  $("#model-filter").focus();
}

function renderOptions(filter = "") {
  const list = $("#model-options");
  const group = currentGroup;
  const terms = filter.toLowerCase().split(/\s+/).filter(Boolean);
  list.replaceChildren();
  entries = [];
  if (!group) return;
  if (group.error) {
    const note = element(
      "li",
      "combobox-note",
      GROUP_ERROR_TEXT[group.error] || "Không tải được danh sách model; gõ ID model để dùng.",
    );
    note.setAttribute("role", "presentation");
    list.append(note);
  }
  const found = group.models.filter((model) => matches(`${model.id} ${model.name}`, terms));
  found.slice(0, PAGE).forEach((model) => {
    const entry = { group, model: model.id, name: model.name };
    list.append(optionNode(entry, entries.push(entry) - 1));
  });
  if (found.length > PAGE) {
    const more = element("li", "combobox-note", `Còn ${found.length - PAGE} model; gõ để lọc.`);
    more.setAttribute("role", "presentation");
    list.append(more);
  }
  // A typed ID comes last so Enter picks a listed match first; it covers models a list omits.
  if (filter && MODEL_ID.test(filter) && !group.models.some((model) => model.id === filter)) {
    const entry = { group, model: filter, name: filter, custom: true };
    list.append(optionNode(entry, entries.push(entry) - 1));
  }
  if (!list.children.length) list.append(element("li", "combobox-note", "Không có model khớp."));
}

function setActive(index) {
  const options = [...$("#model-options").querySelectorAll("[role=option]")];
  active = options.length ? (index + options.length) % options.length : -1;
  options.forEach((node, i) => node.classList.toggle("is-active", i === active));
  const node = options[active];
  if (node) {
    $("#model-filter").setAttribute("aria-activedescendant", node.id);
    node.scrollIntoView({ block: "nearest" });
  } else $("#model-filter").removeAttribute("aria-activedescendant");
}

function open() {
  if (isOpen()) return;
  $("#model-popover").hidden = false;
  $("#model-button").setAttribute("aria-expanded", "true");
  renderProviders();
}

function close({ focus = false } = {}) {
  if (!isOpen()) return;
  $("#model-popover").hidden = true;
  $("#model-button").setAttribute("aria-expanded", "false");
  currentGroup = null;
  active = -1;
  renderPicker();
  if (focus) $("#model-button").focus();
}

function choose(entry) {
  state.ai = { group: entry.group.id, model: entry.model };
  persist();
  close();
  $("#question").focus();
}

// Keep the saved choice when its connection still exists; otherwise pick the first usable model.
async function loadModels({ prefer } = {}) {
  if (!state.user) return;
  const userId = state.user.id;
  const revision = ++modelsRevision;
  state.models = { ...state.models, loading: true };
  renderPicker();
  if (isOpen() && !currentGroup) renderProviders();
  try {
    const result = await api.get("/ai/models");
    if (state.user?.id !== userId || revision !== modelsRevision) return;
    state.models = { ...result, loading: false };
  } catch (error) {
    if (state.user?.id !== userId || revision !== modelsRevision) return;
    state.models = { groups: [], apiKeysAvailable: true, loading: false, error: error.message };
    notify(error.message);
  }
  if (prefer && state.ai?.group !== prefer && groupOf(prefer)?.models.length)
    state.ai = defaultChoice(prefer);
  else if (!selectedGroup()) state.ai = defaultChoice();
  persist();
  renderPicker();
  if (isOpen()) {
    if (currentGroup) {
      currentGroup = groupOf(currentGroup.id) || null;
      if (currentGroup) renderOptions($("#model-filter").value.trim());
      else renderProviders();
    } else renderProviders();
  }
}

function resetModels() {
  modelsRevision++;
  state.models = { groups: [], apiKeysAvailable: true, loading: false };
  close();
  renderPicker();
}

// Request fields for the chosen connection, or null when nothing usable is selected.
function selectedModel() {
  const group = selectedGroup();
  if (!group || RECONNECT_ERRORS.has(group.error) || !state.ai.model) return null;
  return { provider: group.provider, credential_source: group.source, model: state.ai.model };
}

function focusPicker() {
  $("#model-button").focus();
  open();
}

$("#model-button").addEventListener("click", () => (isOpen() ? close() : open()));
$("#model-back").addEventListener("click", () => {
  currentGroup = null;
  renderProviders();
  $("#model-providers").querySelector("button")?.focus();
});
$("#model-filter").addEventListener("input", (event) => {
  renderOptions(event.target.value.trim());
  setActive(0);
});
$("#model-filter").addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    setActive(active + (event.key === "ArrowDown" ? 1 : -1));
  } else if (event.key === "Enter") {
    event.preventDefault();
    if (entries[active]) choose(entries[active]);
  }
});
$(".model-menu").addEventListener("keydown", (event) => {
  if (event.key === "Escape" && isOpen()) {
    event.preventDefault();
    event.stopPropagation();
    close({ focus: true });
  }
});
document.addEventListener("click", (event) => {
  if (isOpen() && !$(".model-menu").contains(event.target)) close();
});

export { focusPicker, loadModels, resetModels, selectedModel };
