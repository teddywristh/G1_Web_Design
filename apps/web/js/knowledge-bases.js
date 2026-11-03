import { api } from "./api.js";
import { $, MAX_KBS, element, isAdmin, notify, persist, state } from "./core.js";
import { loadDocs } from "./documents.js";

// Kho riêng, kho chung và xuất bản
async function loadKbs() {
  try {
    state.kbs = await api.get("/knowledge-bases");
  } catch (error) {
    notify(error.message);
    state.kbs = [];
  }
  const ids = state.kbs.map((kb) => kb.id);
  state.selected = new Set([...state.selected].filter((id) => ids.includes(id)));
  if (!state.kbs.some((kb) => kb.id === state.kbId)) state.kbId = state.kbs[0]?.id || null;
  renderScope();
  renderKbSelect();
}

function kbTitle(kb) {
  return kb.kind === "shared" ? "Kho luật dùng chung" : kb.title;
}

function renderScope() {
  const box = $("#kb-scope");
  box.replaceChildren(element("legend", "", `Nguồn tra cứu (tối đa ${MAX_KBS} kho)`));
  state.kbs.forEach((kb) => {
    const label = element("label", "scope-option");
    const input = element("input");
    input.type = "checkbox";
    input.value = kb.id;
    input.checked = state.selected.has(kb.id);
    input.addEventListener("change", () => {
      if (input.checked && state.selected.size >= MAX_KBS) {
        input.checked = false;
        notify(`Chỉ chọn tối đa ${MAX_KBS} kho cho mỗi câu hỏi.`);
        return;
      }
      if (input.checked) state.selected.add(kb.id);
      else state.selected.delete(kb.id);
      persist();
    });
    label.append(input, element("span", "", kbTitle(kb) + (kb.ready ? "" : " (chưa sẵn sàng)")));
    box.append(label);
  });
  if (!state.kbs.length) box.append(element("p", "small-print", "Chưa có kho nào."));
}

function renderKbSelect() {
  const select = $("#kb-select");
  select.replaceChildren();
  state.kbs.forEach((kb) => select.add(new Option(kbTitle(kb), kb.id)));
  select.value = state.kbId || "";
  renderKbControls();
}

function currentKb() {
  return state.kbs.find((kb) => kb.id === state.kbId);
}

function renderKbControls() {
  const kb = currentKb();
  const shared = kb?.kind === "shared";
  $("#new-kb").hidden = !state.user;
  $("#open-upload").hidden = !kb || (shared && !isAdmin());
  $("#category-tabs").hidden = !shared;
  $("#publish-kb").hidden = !(
    shared &&
    isAdmin() &&
    kb.latestGeneration &&
    kb.latestGeneration !== kb.activeIndexGeneration
  );
  $("#library-note").textContent = !state.user
    ? "Đăng nhập để xem và quản lý tài liệu."
    : shared
      ? "Văn bản do quản trị viên quản lý, dùng chung cho mọi người."
      : "Tài liệu riêng chỉ mình bạn thấy; dùng khi chọn kho này trong hỏi đáp.";
}

$("#kb-select").addEventListener("change", (event) => {
  state.kbId = event.target.value;
  renderKbControls();
  loadDocs(true);
});
$("#new-kb").addEventListener("click", async () => {
  const title = prompt("Tên kho riêng");
  if (!title?.trim()) return;
  try {
    const kb = await api.post("/knowledge-bases", { title: title.trim() });
    state.kbId = kb.id;
    await loadKbs();
    loadDocs(true);
  } catch (error) {
    notify(error.message);
  }
});
$("#publish-kb").addEventListener("click", async () => {
  const kb = currentKb();
  try {
    await api.post(
      `/admin/knowledge-bases/${kb.id}/publish`,
      { generationId: kb.latestGeneration },
      {
        version: kb.version,
      },
    );
    notify("Đã xuất bản bản dựng mới.");
    await loadKbs();
    renderKbControls();
  } catch (error) {
    notify(error.message);
  }
});

export { currentKb, loadKbs, renderKbControls, renderKbSelect, renderScope };
