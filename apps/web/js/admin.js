import { api } from "./api.js";
import { $, element, notify, state } from "./core.js";

let usersCursor = null;
let auditCursor = null;

function renderUsers(items, append = false) {
  const rows = $("#admin-user-rows");
  if (!append) rows.replaceChildren();
  items.forEach((user) => {
    const row = element("tr");
    row.append(
      element("td", "", `${user.displayName} · ${user.email || "Không có email"}`),
      element("td", "", user.role === "admin" ? "Quản trị viên" : "Người dùng"),
      element("td", "", user.isActive ? "Đang hoạt động" : "Đã khóa"),
    );
    const action = element("td");
    const button = element("button", "text-button", user.isActive ? "Khóa" : "Mở khóa");
    button.disabled = user.id === state.user?.id;
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const updated = await api.patch(
          `/admin/users/${user.id}`,
          { isActive: !user.isActive },
          { version: user.version },
        );
        user.isActive = updated.isActive;
        user.version = updated.version;
        button.textContent = user.isActive ? "Khóa" : "Mở khóa";
        const status = row.children[2];
        status.textContent = user.isActive ? "Đang hoạt động" : "Đã khóa";
        button.disabled = user.id === state.user?.id;
        notify(user.isActive ? "Đã mở khóa tài khoản." : "Đã khóa tài khoản.");
      } catch (error) {
        notify(error.message);
        button.disabled = false;
      }
    });
    action.append(button);
    row.append(action);
    rows.append(row);
  });
}

function renderAudit(items, append = false) {
  const list = $("#admin-audit-list");
  if (!append) list.replaceChildren();
  items.forEach((item) => {
    const row = element("li");
    row.append(
      element("span", "", `${item.event} · ${item.result}`),
      element("small", "", new Date(item.createdAt).toLocaleString("vi-VN")),
    );
    list.append(row);
  });
}

async function loadAdmin(reset = true) {
  if (reset) {
    usersCursor = null;
    auditCursor = null;
    $("#admin-users-error").textContent = "";
    $("#admin-audit-error").textContent = "";
  }
  if (reset || usersCursor) try {
    const params = new URLSearchParams({ limit: "20" });
    if (usersCursor) params.set("cursor", usersCursor);
    const page = await api.get(`/admin/users?${params}`);
    renderUsers(page.items, !reset);
    usersCursor = page.nextCursor;
    $("#admin-users-more").hidden = !usersCursor;
  } catch (error) {
    $("#admin-users-error").textContent = error.message;
  }
  if (reset || auditCursor) try {
    const params = new URLSearchParams({ limit: "20" });
    if (auditCursor) params.set("cursor", auditCursor);
    const page = await api.get(`/admin/audit-logs?${params}`);
    renderAudit(page.items, !reset);
    auditCursor = page.nextCursor;
    $("#admin-audit-more").hidden = !auditCursor;
  } catch (error) {
    $("#admin-audit-error").textContent = error.message;
  }
}

$("#admin-users-more").addEventListener("click", () => loadAdmin(false));
$("#admin-audit-more").addEventListener("click", () => loadAdmin(false));

export { loadAdmin };
