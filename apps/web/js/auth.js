import { api, setCsrf } from "./api.js";
import { renderChat } from "./chat.js";
import { $, element, isAdmin, notify, readStore, state, storeKey } from "./core.js";
import { loadKbs, renderKbSelect, renderScope } from "./knowledge-bases.js";
import { navigate } from "./navigation.js";
import { loadConnections } from "./settings.js";

let googleTimer;

// Đăng nhập, đăng ký và khôi phục phiên
function showAuth(message = "") {
  state.user = null;
  $("#auth-view").hidden = false;
  $("#sidebar").hidden = true;
  $("#app-shell").hidden = true;
  $("#auth-error").textContent = message;
}

function showGuest(message = "") {
  state.user = null;
  state.kbs = [];
  state.kbId = null;
  state.docs = [];
  state.selected = new Set();
  state.chats = readStore("chats", []);
  state.chatId = null;
  state.saved = new Set(readStore("saved", []));
  $("#auth-view").hidden = true;
  $("#sidebar").hidden = false;
  $("#app-shell").hidden = false;
  $("#user-name").textContent = "Khách trải nghiệm";
  $("#user-role").textContent = "Đăng nhập để sử dụng AI";
  $("#account-action").textContent = "Đăng nhập";
  $("#register-action").hidden = false;
  $("#backend-label").textContent = "Chế độ trải nghiệm";
  renderScope();
  renderKbSelect();
  renderChat();
  navigate("chat");
  if (message) notify(message);
}

function setAuthMode(mode) {
  state.authMode = mode;
  const register = mode === "register";
  $("#auth-title").textContent = register ? "Tạo tài khoản" : "Đăng nhập Legal AI";
  $("#auth-submit").textContent = register ? "Đăng ký" : "Đăng nhập";
  $("#auth-switch").textContent = register
    ? "Đã có tài khoản? Đăng nhập"
    : "Chưa có tài khoản? Đăng ký";
  $("#name-field").hidden = !register;
  $("#name-field input").required = register;
  $("#confirm-field").hidden = !register;
  $("#confirm-field input").required = register;
  $("#auth-form [name=password]").minLength = register ? 8 : 1;
  $("#auth-form [name=password]").autocomplete = register ? "new-password" : "current-password";
}

async function enterSession(session) {
  setCsrf(session.csrfToken);
  state.user = session.user;
  state.chats = readStore("chats", []);
  state.saved = new Set(readStore("saved", []));
  const prefs = readStore("prefs", {});
  state.selected = new Set(prefs.kbs || []);
  $("#provider").value = prefs.provider || "openai";
  $("#model").value = prefs.model || "";
  $("#engine").value = prefs.engine || "direct";
  $("#credential-source").value = prefs.credentialSource || "auto";
  $("#retrieval-mode").value = prefs.retrievalMode || "hybrid";
  $("#as-of").value = "";
  $("#auth-view").hidden = true;
  $("#sidebar").hidden = false;
  $("#app-shell").hidden = false;
  $("#user-name").textContent = state.user.displayName;
  $("#user-role").textContent = isAdmin() ? "Quản trị viên" : "Người dùng";
  $("#account-action").textContent = "Tài khoản";
  $("#register-action").hidden = true;
  $("#backend-label").textContent = "Đã kết nối";
  $("#account-info").textContent = `${state.user.displayName} · ${state.user.email || ""}`;
  await loadKbs();
  await loadConnections({ restore: !prefs.credentialSource });
  renderChat();
  navigate("chat");
  if (window.google?.accounts?.id) setupGoogle();
}

async function boot() {
  setAuthMode("login");
  try {
    await enterSession(await api.get("/auth/me"));
  } catch (error) {
    showGuest(error.status === 0 ? error.message : "");
  }
  setupGoogle();
}

async function setupGoogle() {
  clearTimeout(googleTimer);
  let challenge;
  try {
    challenge = await api.get("/auth/google/challenge");
  } catch {
    return;
  }
  const clientId =
    document.querySelector('meta[name="google-client-id"]').content || challenge.clientId;
  if (!clientId) return;
  const render = () => {
    try {
      const { nonce } = challenge;
      google.accounts.id.initialize({
        client_id: clientId,
        nonce,
        callback: async (response) => {
          try {
            await enterSession(await api.post("/auth/google", { credential: response.credential }));
          } catch (error) {
            if (state.user) notify(error.message);
            else $("#auth-error").textContent = error.message;
            setupGoogle();
          }
        },
      });
      $("#google-button").replaceChildren();
      $("#google-link-button").replaceChildren();
      google.accounts.id.renderButton($("#google-button"), { theme: "outline", size: "large" });
      google.accounts.id.renderButton($("#google-link-button"), {
        theme: "outline",
        size: "large",
      });
      googleTimer = setTimeout(setupGoogle, 240000);
    } catch {
      /* Google sign-in is optional; email sign-in still works. */
    }
  };
  if (window.google?.accounts?.id) render();
  else if (!document.querySelector("script[data-google-identity]")) {
    const script = element("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.dataset.googleIdentity = "true";
    script.onload = render;
    document.head.append(script);
  }
}

$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const register = state.authMode === "register";
  const body = { email: String(data.get("email")), password: String(data.get("password")) };
  if (register) body.displayName = String(data.get("displayName")).trim();
  if (new TextEncoder().encode(body.password).length > 72) {
    $("#auth-error").textContent = "Mật khẩu tối đa 72 byte UTF-8.";
    return;
  }
  if (register && body.password !== String(data.get("confirmation"))) {
    $("#auth-error").textContent = "Mật khẩu xác nhận không khớp.";
    return;
  }
  $("#auth-submit").disabled = true;
  try {
    const session = await api.post(register ? "/auth/register" : "/auth/login", body);
    form.reset();
    await enterSession(session);
  } catch (error) {
    $("#auth-error").textContent =
      error.status === 401 ? "Email hoặc mật khẩu không đúng." : error.message;
  } finally {
    $("#auth-submit").disabled = false;
  }
});
$("#auth-switch").addEventListener("click", () =>
  setAuthMode(state.authMode === "login" ? "register" : "login"),
);
$("#guest-back").addEventListener("click", () => showGuest());
$("#register-action").addEventListener("click", () => {
  setAuthMode("register");
  showAuth();
});

async function logout(all) {
  try {
    await api.post(all ? "/auth/logout-all" : "/auth/logout", {});
  } catch {
    /* Even if the server call fails, drop local state. */
  }
  clearTimeout(state.pollTimer);
  // Chat history and cited text must not outlive the session on a shared computer.
  ["chats", "saved", "prefs"].forEach((name) => localStorage.removeItem(storeKey(name)));
  Object.assign(state, { kbs: [], docs: [], chats: [], chatId: null, saved: new Set() });
  Object.assign(state, {
    selected: new Set(),
    connections: [],
    kbId: null,
    aiOptions: null,
    chatgpt: { connected: false, pending: false },
    sessions: [],
    sessionCursor: null,
  });
  setCsrf("");
  $("#messages").replaceChildren();
  showGuest();
  setupGoogle();
}
$("#logout").addEventListener("click", () => logout(false));
$("#logout-all").addEventListener("click", () => logout(true));

export { boot, setAuthMode, showAuth };
