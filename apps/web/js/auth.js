import { api, setCsrf } from "./api.js";
import { renderChat } from "./chat.js";
import { $, element, isAdmin, notify, readStore, state, storeKey } from "./core.js";
import { loadKbs, renderKbSelect, renderScope } from "./knowledge-bases.js";
import { closeMenu, navigate } from "./navigation.js";
import { loadModels, resetModels } from "./models.js";
import { loadConnections } from "./settings.js";

let googleTimer;

// Đăng nhập, đăng ký và khôi phục phiên
function showAuth(message = "") {
  closeMenu();
  state.user = null;
  document.dispatchEvent(new Event("close-evidence"));
  $("#auth-view").hidden = false;
  $("#login-action").hidden = true;
  $("#sidebar").hidden = true;
  $("#app-shell").hidden = true;
  $("#auth-error").textContent = "";
  $("#auth-notice").textContent = message;
  $("#auth-notice").hidden = !message;
}

function showGuest(message = "") {
  document.dispatchEvent(new Event("close-evidence"));
  state.pendingChat = null;
  state.chatError = null;
  state.user = null;
  state.kbs = [];
  state.kbId = null;
  state.docs = [];
  state.chats = readStore("chats", []);
  state.chatId = null;
  state.saved = new Set(readStore("saved", []));
  $("#auth-view").hidden = true;
  $("#login-action").hidden = false;
  $("#sidebar").hidden = false;
  $("#app-shell").hidden = false;
  $("#user-name").textContent = "Khách trải nghiệm";
  $("#user-role").textContent = "Đăng nhập để sử dụng AI";
  renderScope();
  renderKbSelect();
  renderChat();
  navigate("chat");
  if (message) notify(message);
}

function setAuthMode(mode) {
  state.authMode = mode;
  const register = mode === "register";
  const recovery = mode === "forgot" || mode === "reset";
  $("#auth-title").textContent = recovery
    ? "Khôi phục mật khẩu"
    : register
      ? "Tạo tài khoản"
      : "Đăng nhập Legal AI";
  $("#auth-submit").textContent =
    mode === "forgot"
      ? "Gửi mã OTP"
      : mode === "reset"
        ? "Đổi mật khẩu"
        : register
          ? "Đăng ký"
          : "Đăng nhập";
  $("#auth-description").textContent = recovery
    ? "Nhận mã xác nhận qua email đã đăng ký."
    : register
      ? "Một tài khoản để lưu tài liệu và tra cứu thuận tiện."
      : "Đăng nhập để hỏi đáp và quản lý tài liệu của bạn.";
  $("#auth-switch").textContent = register
    ? "Đã có tài khoản? Đăng nhập"
    : "Chưa có tài khoản? Đăng ký";
  $("#name-field").hidden = !register;
  $("#name-field input").required = register;
  $("#name-field input").disabled = !register;
  $("#confirm-field").hidden = !(register || mode === "reset");
  $("#confirm-field input").required = register || mode === "reset";
  $("#confirm-field input").disabled = !(register || mode === "reset");
  $("#password-field").hidden = mode === "forgot";
  $("#auth-form [name=password]").required = mode !== "forgot";
  $("#auth-form [name=password]").disabled = mode === "forgot";
  $("#auth-form [name=password]").minLength = mode === "login" ? 1 : 8;
  $("#auth-form [name=password]").autocomplete =
    mode === "login" ? "current-password" : "new-password";
  $("#otp-field").hidden = mode !== "reset";
  $("#otp-field input").required = mode === "reset";
  $("#otp-field input").disabled = mode !== "reset";
  $("#auth-forgot").hidden = mode !== "login";
  $("#google-button").hidden = recovery;
  $("#resend-otp").hidden = mode !== "reset";
  $("#auth-error").textContent = "";
  $("#auth-notice").hidden = true;
  if (recovery) $("#auth-switch").textContent = "Quay lại đăng nhập";
}

async function enterSession(session) {
  setCsrf(session.csrfToken);
  state.user = session.user;
  $("#login-action").hidden = true;
  state.chats = readStore("chats", []);
  state.saved = new Set(readStore("saved", []));
  const prefs = readStore("prefs", {});
  state.ai = prefs.ai || null;
  $("#as-of").value = "";
  $("#auth-view").hidden = true;
  $("#sidebar").hidden = false;
  $("#app-shell").hidden = false;
  $("#user-name").textContent = state.user.displayName;
  $("#user-role").textContent = isAdmin() ? "Quản trị viên" : "Người dùng";
  $("#account-info").textContent = `${state.user.displayName} · ${state.user.email || ""}`;
  await loadKbs();
  // Listing can wait on a ChatGPT worker restore; the picker shows its own loading state.
  loadModels();
  await loadConnections();
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
  if (form.getAttribute("aria-busy") === "true") return;
  const data = new FormData(form);
  const register = state.authMode === "register";
  const mode = state.authMode;
  const body = {
    email: String(data.get("email")).trim().toLowerCase(),
    password: String(data.get("password") || ""),
  };
  if (register) body.displayName = String(data.get("displayName")).trim();
  if (new TextEncoder().encode(body.password).length > 72) {
    $("#auth-error").textContent = "Mật khẩu tối đa 72 byte UTF-8.";
    return;
  }
  if ((register || mode === "reset") && body.password !== String(data.get("confirmation"))) {
    $("#auth-error").textContent = "Mật khẩu xác nhận không khớp.";
    return;
  }
  $("#auth-submit").disabled = true;
  $("#auth-error").textContent = "";
  const label = $("#auth-submit").textContent;
  $("#auth-submit").textContent = mode === "forgot" ? "Đang gửi mã…" : "Đang xử lý…";
  form.setAttribute("aria-busy", "true");
  ["auth-switch", "auth-forgot", "guest-back", "resend-otp"].forEach((id) => {
    $("#" + id).disabled = true;
  });
  try {
    if (mode === "forgot") {
      const result = await api.post("/auth/password/otp", { email: body.email });
      setAuthMode("reset");
      $("#auth-notice").textContent = result.message;
      $("#auth-notice").hidden = false;
      $("#otp-field input").focus();
      return;
    }
    if (mode === "reset") {
      await api.post("/auth/password/reset", { ...body, otp: String(data.get("otp")) });
      form.reset();
      setAuthMode("login");
      $("#auth-notice").textContent = "Đã đổi mật khẩu. Hãy đăng nhập bằng mật khẩu mới.";
      $("#auth-notice").hidden = false;
      return;
    }
    const session = await api.post(register ? "/auth/register" : "/auth/login", body);
    form.reset();
    await enterSession(session);
  } catch (error) {
    $("#auth-error").textContent =
      error.status === 401 ? "Email hoặc mật khẩu không đúng." : error.message;
  } finally {
    $("#auth-submit").disabled = false;
    form.removeAttribute("aria-busy");
    ["auth-switch", "auth-forgot", "guest-back", "resend-otp"].forEach((id) => {
      $("#" + id).disabled = false;
    });
    if (state.authMode === mode) $("#auth-submit").textContent = label;
  }
});
$("#auth-switch").addEventListener("click", () =>
  setAuthMode(state.authMode === "login" ? "register" : "login"),
);
$("#auth-forgot").addEventListener("click", () => setAuthMode("forgot"));
$("#resend-otp").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  $("#auth-error").textContent = "";
  try {
    const result = await api.post("/auth/password/otp", {
      email: $("#auth-form [name=email]").value.trim().toLowerCase(),
    });
    $("#auth-notice").textContent = result.message;
    $("#auth-notice").hidden = false;
  } catch (error) {
    $("#auth-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
$("#guest-back").addEventListener("click", () => showGuest());
$("#login-action").addEventListener("click", () => {
  setAuthMode("login");
  showAuth();
});

async function logout(all) {
  try {
    await api.post(all ? "/auth/logout-all" : "/auth/logout", {});
  } catch (error) {
    if (error.status !== 401) {
      notify("Chưa đăng xuất được trên máy chủ. " + error.message);
      return;
    }
  }
  clearTimeout(state.pollTimer);
  // Chat history and cited text must not outlive the session on a shared computer.
  // Keep only non-secret per-account connection preferences; credentials stay on the backend.
  ["chats", "saved"].forEach((name) => localStorage.removeItem(storeKey(name)));
  Object.assign(state, { kbs: [], docs: [], chats: [], chatId: null, saved: new Set() });
  Object.assign(state, {
    connections: [],
    kbId: null,
    aiOptions: null,
    chatgpt: { connected: false, pending: false },
    ai: null,
    sessions: [],
    sessionCursor: null,
  });
  setCsrf("");
  $("#messages").replaceChildren();
  resetModels();
  showGuest();
  setupGoogle();
}
$("#logout").addEventListener("click", () => logout(false));
$("#logout-all").addEventListener("click", () => logout(true));

export { boot, setAuthMode, showAuth };
