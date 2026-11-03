import { api } from "./api.js";
import { $, element, state } from "./core.js";
import { navigate } from "./navigation.js";

async function loadSessions(cursor) {
  if (!state.user) return;
  const userId = state.user.id;
  try {
    const page = await api.get(
      `/auth/sessions${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
    );
    if (state.user?.id !== userId) return;
    state.sessions = cursor ? [...state.sessions, ...page.items] : page.items;
    state.sessionCursor = page.nextCursor;
    $("#session-error").textContent = "";
    const list = $("#session-list");
    list.replaceChildren();
    state.sessions.forEach((session) => {
      const row = element("li");
      const title = session.current ? "Thiết bị này" : "Phiên khác";
      const expires = session.active
        ? `Hết hạn ${new Date(session.expiresAt).toLocaleString("vi-VN")}`
        : "Đã hết hạn hoặc thu hồi";
      row.append(element("span", "", `${title} · ${expires}`));
      if (!session.current && session.active) {
        const button = element("button", "text-button danger", "Thu hồi");
        button.addEventListener("click", async () => {
          button.disabled = true;
          try {
            await api.del(`/auth/sessions/${encodeURIComponent(session.id)}`);
            await loadSessions();
          } catch (error) {
            $("#session-error").textContent = error.message;
            button.disabled = false;
          }
        });
        row.append(button);
      }
      list.append(row);
    });
    $("#sessions-more").hidden = !state.sessionCursor;
  } catch (error) {
    $("#session-error").textContent = error.message;
  }
}
$("#sessions-more").addEventListener("click", () => loadSessions(state.sessionCursor));
document.querySelectorAll("[data-settings-target]").forEach((button) =>
  button.addEventListener("click", () => {
    navigate("settings");
    const target = document.getElementById(button.dataset.settingsTarget);
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    target.focus({ preventScroll: true });
  }),
);

export { loadSessions };
