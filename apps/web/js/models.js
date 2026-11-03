import { api } from "./api.js";
import { $, element, notify, persist, state } from "./core.js";

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
let entries = [];
let active = -1;

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
  const groups = state.models.groups.filter((group) => group.models.length);
  const group = groups.find((item) => item.id === prefer) || groups[0];
  if (!group) return null;
  const preferred = group.models.find((model) => model.id === PREFERRED[group.id]);
  return { group: group.id, model: (preferred || group.models[0]).id };
}

function selectedGroup() {
  return groupOf(state.ai?.group);
}

function placeholder() {
  if (state.models.loading) return "Đang tải model…";
  if (!state.models.groups.length) return "Chưa có kết nối AI";
  return "Chọn nhà cung cấp và model";
}

function renderPicker() {
  const input = $("#model-picker");
  input.placeholder = placeholder();
  if (input.getAttribute("aria-expanded") !== "true") input.value = choiceLabel(state.ai);
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

function renderOptions(filter = "") {
  const list = $("#model-options");
  const terms = filter.toLowerCase().split(/\s+/).filter(Boolean);
  list.replaceChildren();
  entries = [];
  if (!state.models.groups.length) {
    const note = state.models.apiKeysAvailable
      ? "Thêm API key hoặc kết nối ChatGPT trong Thiết lập → Kết nối AI."
      : "Máy chủ chưa bật OpenCode cho API key. Kết nối ChatGPT trong Thiết lập, hoặc liên hệ quản trị viên.";
    list.append(element("li", "combobox-note", state.models.loading ? "Đang tải model…" : note));
    return;
  }
  const heading = (title, detail) => {
    const node = element("li", "combobox-group");
    node.setAttribute("role", "presentation");
    node.append(element("strong", "", title), element("small", "", detail));
    list.append(node);
  };
  state.models.groups.forEach((group) => {
    const header = `${group.label} ${SOURCE_TEXT[group.source] || ""}`;
    const headerMatches = terms.length > 0 && matches(header, terms);
    const found = group.models.filter(
      (model) => headerMatches || matches(`${header} ${model.id} ${model.name}`, terms),
    );
    if (terms.length && !found.length) return;
    heading(group.label, SOURCE_TEXT[group.source] || group.source);
    if (group.error) {
      const note = element(
        "li",
        "combobox-note",
        GROUP_ERROR_TEXT[group.error] || "Không tải được danh sách model; gõ ID model để dùng.",
      );
      note.setAttribute("role", "presentation");
      list.append(note);
    }
    found.slice(0, PAGE).forEach((model) => {
      const entry = { group, model: model.id, name: model.name };
      list.append(optionNode(entry, entries.push(entry) - 1));
    });
    if (found.length > PAGE) {
      const more = element("li", "combobox-note", `Còn ${found.length - PAGE} model; gõ để lọc.`);
      more.setAttribute("role", "presentation");
      list.append(more);
    }
  });
  // Typed IDs come last so Enter picks a listed match first; they cover models a list omits.
  const exact = state.models.groups.some((group) =>
    group.models.some((model) => model.id === filter),
  );
  if (filter && MODEL_ID.test(filter) && !exact) {
    heading("Dùng ID tự nhập", filter);
    state.models.groups.forEach((group) => {
      const entry = { group, model: filter, name: group.label, custom: true };
      list.append(optionNode(entry, entries.push(entry) - 1));
    });
  }
  if (!list.children.length) list.append(element("li", "combobox-note", "Không có model khớp."));
}

function setActive(index) {
  const options = [...$("#model-options").querySelectorAll("[role=option]")];
  active = options.length ? (index + options.length) % options.length : -1;
  options.forEach((node, i) => node.classList.toggle("is-active", i === active));
  const node = options[active];
  if (node) {
    $("#model-picker").setAttribute("aria-activedescendant", node.id);
    node.scrollIntoView({ block: "nearest" });
  } else $("#model-picker").removeAttribute("aria-activedescendant");
}

function open() {
  const input = $("#model-picker");
  if (input.getAttribute("aria-expanded") === "true") return;
  input.setAttribute("aria-expanded", "true");
  input.value = "";
  renderOptions();
  $("#model-options").hidden = false;
  setActive(
    entries.findIndex(
      (entry) => entry.group.id === state.ai?.group && entry.model === state.ai?.model,
    ),
  );
}

function close() {
  const input = $("#model-picker");
  input.setAttribute("aria-expanded", "false");
  input.removeAttribute("aria-activedescendant");
  $("#model-options").hidden = true;
  active = -1;
  renderPicker();
}

function choose(entry) {
  state.ai = { group: entry.group.id, model: entry.model };
  persist();
  close();
}

// Keep the saved choice when its connection still exists; otherwise pick the first usable model.
async function loadModels({ prefer } = {}) {
  if (!state.user) return;
  const userId = state.user.id;
  state.models = { ...state.models, loading: true };
  renderPicker();
  try {
    const result = await api.get("/ai/models");
    if (state.user?.id !== userId) return;
    state.models = { ...result, loading: false };
  } catch (error) {
    if (state.user?.id !== userId) return;
    state.models = { groups: [], apiKeysAvailable: true, loading: false };
    notify(error.message);
  }
  if (prefer && state.ai?.group !== prefer && groupOf(prefer)?.models.length)
    state.ai = defaultChoice(prefer);
  else if (!selectedGroup()) state.ai = defaultChoice();
  persist();
  renderPicker();
  if ($("#model-picker").getAttribute("aria-expanded") === "true")
    renderOptions($("#model-picker").value.trim());
}

function resetModels() {
  state.models = { groups: [], apiKeysAvailable: true, loading: false };
  close();
}

// Request fields for the chosen connection, or null when nothing usable is selected.
function selectedModel() {
  const group = selectedGroup();
  if (!group || !state.ai.model) return null;
  return { provider: group.provider, credential_source: group.source, model: state.ai.model };
}

function focusPicker() {
  $("#model-picker").focus();
  open();
}

$("#model-picker").addEventListener("focus", open);
$("#model-picker").addEventListener("click", open);
$("#model-picker").addEventListener("blur", close);
$("#model-picker").addEventListener("input", (event) => {
  event.target.setAttribute("aria-expanded", "true");
  $("#model-options").hidden = false;
  renderOptions(event.target.value.trim());
  setActive(0);
});
$("#model-picker").addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    if ($("#model-picker").getAttribute("aria-expanded") !== "true") open();
    else setActive(active + (event.key === "ArrowDown" ? 1 : -1));
  } else if (event.key === "Enter") {
    event.preventDefault();
    if (entries[active]) choose(entries[active]);
  } else if (event.key === "Escape") {
    event.preventDefault();
    $("#model-picker").blur();
  }
});
// Keep focus in the input while clicking an option so blur does not close the list first.
$("#model-options").addEventListener("mousedown", (event) => event.preventDefault());

export { focusPicker, loadModels, resetModels, selectedModel };
