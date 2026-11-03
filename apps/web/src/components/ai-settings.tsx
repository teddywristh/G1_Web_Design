"use client";

import { useEffect, useState, type FormEvent } from "react";
import { KeyRound, ShieldCheck } from "lucide-react";
import { useAiSession } from "@/lib/ai-session";
import { GoogleSignIn } from "@/components/google-sign-in";
import { AccountSessions } from "@/components/account-sessions";

type Connection = {
  provider: "openai" | "anthropic" | "deepseek" | "openrouter";
  scope: "personal" | "shared";
  configured: boolean;
  enabled: boolean;
  version: number;
  origin: string;
};
type Options = {
  credentialStorageReady: boolean;
  connections: Connection[];
  engines?: { opencode: boolean; opencodeApiKeys: boolean };
  methods?: { id: string; available: boolean }[];
};

export function AiSettings({
  connected,
  onLogin,
  onConnect,
  authMode,
  setAuthMode,
}: {
  connected: boolean | null;
  onLogin: () => void;
  onConnect: () => void;
  authMode: "login" | "register";
  setAuthMode: (mode: "login" | "register") => void;
}) {
  const { profile, restoring, choice, setChoice, request, signIn, signUp, signInGoogle, signOut } =
    useAiSession();
  const [options, setOptions] = useState<Options | null>(null);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [password, setPassword] = useState("");
  const [key, setKey] = useState("");
  const [scope, setScope] = useState<"personal" | "shared">("personal");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [chatgpt, setChatgpt] = useState<{connected: boolean; pending?: boolean; url?: string; instructions?: string}>({connected: false});
  const chatgptAvailable = Boolean(options?.methods?.find((item) => item.id === "chatgpt_oauth")?.available);

  useEffect(() => {
    let cancelled = false;
    setOptions(null);
    setKey("");
    setScope("personal");
    setMessage("");
    setChatgpt({connected: false});
    if (profile)
      request<Options>("/api/v1/ai/connections")
        .then((value) => {
          if (!cancelled) setOptions(value);
        })
        .catch((error) => {
          if (!cancelled)
            setMessage(error instanceof Error ? error.message : "Không tải được kết nối.");
        });
    return () => {
      cancelled = true;
    };
  }, [profile, request]);

  useEffect(() => {
    let active = true;
    if (profile && chatgptAvailable) {
      request<{connected: boolean; pending: boolean}>("/api/v1/ai/chatgpt")
        .then((value) => { if (active) setChatgpt(value); })
        .catch(() => { if (active) setChatgpt({connected: false}); });
    }
    return () => { active = false; };
  }, [profile, chatgptAvailable, request]);

  async function chatgptAction(action: "start" | "finish" | "disconnect") {
    setBusy(true);
    setMessage("");
    try {
      const result = await request<{connected: boolean; pending?: boolean; url?: string; instructions?: string}>(
        action === "disconnect" ? "/api/v1/ai/chatgpt" : `/api/v1/ai/chatgpt/${action}`,
        {method: action === "disconnect" ? "DELETE" : "POST", body: action === "disconnect" ? undefined : "{}", signal: AbortSignal.timeout(action === "finish" ? 260000 : 130000)},
      );
      setChatgpt({...result, pending: action === "start"});
      if (action === "finish" && result.connected) {
        setChoice({...choice, provider: "openai", engine: "opencode", credential_source: "chatgpt", retrieval_mode: "keyword", model: "gpt-5.6-luna"});
        setMessage("Đã kết nối ChatGPT cho phiên local này.");
      }
      if (action === "disconnect" && choice.credential_source === "chatgpt")
        setChoice({...choice, credential_source: "auto"});
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Không kết nối được ChatGPT.");
    } finally { setBusy(false); }
  }

  const connection = options?.connections.find(
    (item) => item.provider === choice.provider && item.scope === scope,
  );

  async function login(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      if (new TextEncoder().encode(password).length > 72)
        throw new Error("Mật khẩu tối đa 72 byte UTF-8.");
      if (authMode === "register") {
        if (password !== confirmation) throw new Error("Mật khẩu xác nhận không khớp.");
        await signUp(displayName, email, password);
      } else await signIn(email, password);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Không đăng nhập được.");
    } finally {
      setPassword("");
      setConfirmation("");
      setBusy(false);
    }
  }

  async function googleLogin(credential: string) {
    setBusy(true);
    setMessage("");
    try {
      await signInGoogle(credential);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Không đăng nhập Google được.");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    setMessage("");
    try {
      await signOut();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Không đăng xuất được.");
    } finally {
      setBusy(false);
    }
  }

  async function change(remove = false) {
    if (!connection) return;
    setBusy(true);
    setMessage("");
    const path = `${scope === "shared" ? "/api/v1/admin" : "/api/v1"}/ai/connections/${choice.provider}`;
    try {
      await request(
        path,
        remove
          ? { method: "DELETE", headers: { "If-Match": String(connection.version) } }
          : {
              method: "PUT",
              body: JSON.stringify({
                apiKey: key,
                expectedVersion: connection.version,
                enabled: true,
              }),
            },
      );
      setKey("");
      setOptions(await request<Options>("/api/v1/ai/connections"));
      setMessage(
        remove
          ? "Đã gỡ kết nối."
          : "Đã lưu key. Key sẽ được kiểm tra khi gửi yêu cầu tới nhà cung cấp.",
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Không lưu được kết nối.");
      // Refresh versions after conflicts without retrying or changing the billing source.
      try {
        setOptions(await request<Options>("/api/v1/ai/connections"));
      } catch {
        /* Keep the visible error. */
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section
        className="settings-card ai-settings"
        id="account-settings"
        tabIndex={-1}
        aria-labelledby="account-settings-title"
      >
        <ShieldCheck size={28} />
        <h2 id="account-settings-title">Tài khoản dự án</h2>
        <p className="small-print">
          Backend:{" "}
          {connected === null ? "đang kiểm tra" : connected ? "đã kết nối" : "chưa kết nối"}
        </p>
        {profile ? (
          <>
            <p>
              {profile.displayName} · {profile.email} ·{" "}
              {profile.role === "admin" ? "Quản trị viên" : "Người dùng"}
            </p>
            <div className="ai-actions">
              <button className="secondary-button" onClick={onConnect}>
                Quản lý kết nối AI
              </button>
              <button className="secondary-button" onClick={() => void logout()} disabled={busy}>
                Đăng xuất
              </button>
            </div>
            <p className="small-print">Liên kết Google với tài khoản hiện tại:</p>
            <GoogleSignIn
              onCredential={(credential) => void googleLogin(credential)}
              disabled={busy}
            />
            <AccountSessions />
          </>
        ) : restoring ? (
          <p>Đang kiểm tra phiên đăng nhập…</p>
        ) : (
          <form onSubmit={login} className="ai-form">
            <p>
              {authMode === "register"
                ? "Tạo tài khoản để sử dụng ứng dụng."
                : "Đăng nhập tài khoản dự án để kết nối AI."}
            </p>
            {authMode === "register" && (
              <label>
                Họ và tên
                <input
                  autoComplete="name"
                  value={displayName}
                  minLength={1}
                  maxLength={120}
                  required
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </label>
            )}
            <label>
              Email
              <input
                id="account-email"
                type="email"
                autoComplete="username"
                value={email}
                required
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label>
              Mật khẩu
              <input
                type="password"
                autoComplete={authMode === "register" ? "new-password" : "current-password"}
                minLength={authMode === "register" ? 8 : 1}
                maxLength={72}
                value={password}
                required
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {authMode === "register" && (
              <label>
                Xác nhận mật khẩu
                <input
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  maxLength={72}
                  value={confirmation}
                  required
                  onChange={(e) => setConfirmation(e.target.value)}
                />
              </label>
            )}
            <button className="header-account-button" disabled={busy} type="submit">
              {busy
                ? "Đang xử lý…"
                : authMode === "register"
                  ? "Đăng ký tài khoản"
                  : "Đăng nhập tài khoản"}
            </button>
            <button
              className="auth-mode-link"
              type="button"
              onClick={() => {
                setPassword("");
                setConfirmation("");
                setMessage("");
                setAuthMode(authMode === "register" ? "login" : "register");
              }}
            >
              {authMode === "register"
                ? "Đã có tài khoản? Đăng nhập"
                : "Chưa có tài khoản? Đăng ký"}
            </button>
            <div className="auth-divider">hoặc</div>
            <GoogleSignIn
              onCredential={(credential) => void googleLogin(credential)}
              disabled={busy}
            />
          </form>
        )}
        {message && (
          <p role="status" className="ai-message">
            {message}
          </p>
        )}
      </section>
      <section
        className="settings-card ai-settings"
        id="ai-settings"
        tabIndex={-1}
        aria-labelledby="ai-settings-title"
      >
        <KeyRound size={28} />
        <h2 id="ai-settings-title">Kết nối AI</h2>
        <p>Chọn nhà cung cấp và dùng key cá nhân hoặc key chung của hệ thống.</p>
        {!profile && (
          <div className="ai-login-prompt">
            <p>Đăng nhập tài khoản dự án để thêm hoặc quản lý kết nối AI.</p>
            <button className="secondary-button" onClick={onLogin}>
              Đăng nhập để kết nối
            </button>
          </div>
        )}
        <div className="ai-form">
          <label>
            Nhà cung cấp
            <select
              value={choice.provider}
              onChange={(e) => {
                setChoice({
                  ...choice,
                  provider: e.target.value as typeof choice.provider,
                  credential_source: choice.credential_source === "chatgpt" ? "auto" : choice.credential_source,
                  engine: "direct",
                  model: "",
                });
                setKey("");
              }}
            >
              <option value="openai">OpenAI API</option>
              <option value="anthropic">Claude API (Anthropic)</option>
              <option value="deepseek">DeepSeek API</option>
              <option value="openrouter">OpenRouter API</option>
            </select>
          </label>
          <label>
            Engine xử lý
            <select
              value={choice.engine}
              onChange={(e) => {
                if (e.target.value === "opencode" && !options?.engines?.opencodeApiKeys) {
                  if (!chatgpt.connected || choice.provider !== "openai") {
                    setMessage("Hãy kết nối ChatGPT trước khi dùng OpenCode.");
                    return;
                  }
                  setChoice({...choice, engine: "opencode", credential_source: "chatgpt", model: "gpt-5.6-luna"});
                  return;
                }
                setChoice({
                  ...choice,
                  engine: e.target.value as typeof choice.engine,
                  credential_source: e.target.value === "direct" && choice.credential_source === "chatgpt" ? "auto" : choice.credential_source,
                  retrieval_mode: e.target.value === "opencode" ? "keyword" : choice.retrieval_mode,
                });
              }}
            >
              <option value="direct">Gọi model trực tiếp</option>
              <option
                value="opencode"
                disabled={!options?.engines?.opencode || choice.provider === "anthropic" || (!options.engines.opencodeApiKeys && choice.provider !== "openai")}
              >
                OpenCode (thử nghiệm local)
              </option>
            </select>
          </label>
          <label>
            Nguồn key cho câu hỏi
            <select
              value={choice.credential_source}
              onChange={(e) =>
                setChoice({
                  ...choice,
                  credential_source: e.target.value as typeof choice.credential_source,
                  retrieval_mode: e.target.value === "chatgpt" ? "keyword" : choice.retrieval_mode,
                })
              }
            >
              <option value="auto" disabled={choice.engine === "opencode" && !options?.engines?.opencodeApiKeys}>
                Tự động: cá nhân trước, key chung khi chưa có key cá nhân
              </option>
              <option value="personal" disabled={choice.engine === "opencode" && !options?.engines?.opencodeApiKeys}>Chỉ key cá nhân</option>
              <option value="shared" disabled={choice.engine === "opencode" && !options?.engines?.opencodeApiKeys}>Chỉ key chung của hệ thống</option>
              {choice.provider === "openai" && choice.engine === "opencode" && chatgptAvailable && (
                <option value="chatgpt" disabled={!chatgpt.connected}>ChatGPT Plus/Pro cá nhân</option>
              )}
            </select>
          </label>
          <label>
            Model
            <input
              value={choice.model}
              maxLength={200}
              placeholder={
                choice.provider === "openai"
                  ? "Để trống dùng model mặc định"
                  : choice.provider === "anthropic" ? "Nhập ID model Claude được cấp trong Console" : "Nhập ID model của nhà cung cấp"
              }
              onChange={(e) => setChoice({ ...choice, model: e.target.value })}
            />
          </label>
          <label>
            Cách tra cứu
            <select
              value={choice.retrieval_mode}
              onChange={(e) =>
                setChoice({
                  ...choice,
                  retrieval_mode: e.target.value as typeof choice.retrieval_mode,
                })
              }
            >
              <option value="hybrid" disabled={choice.credential_source === "chatgpt"}>
                Kết hợp ngữ nghĩa + từ khóa (cần key OpenAI cho embeddings)
              </option>
              <option value="keyword">Từ khóa (không gọi API embeddings)</option>
            </select>
          </label>
          {profile && (
            <>
              <label>
                Key muốn quản lý
                <select
                  value={scope}
                  onChange={(e) => {
                    setScope(e.target.value as typeof scope);
                    setKey("");
                  }}
                >
                  <option value="personal">Key riêng của tôi</option>
                  {profile.role === "admin" && (
                    <option value="shared">Key dùng chung cho hệ thống</option>
                  )}
                </select>
              </label>
              <p>
                {connection?.configured
                  ? connection.enabled
                    ? "Đã có key đang bật"
                    : "Đã có cấu hình nhưng đang tắt"
                  : "Chưa có key"}
              </p>
              {!options?.credentialStorageReady && (
                <p className="small-print">
                  Chưa bật kho lưu key. Quản trị viên cần cấu hình mã hóa trên server.
                </p>
              )}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void change();
                }}
                className="ai-form"
              >
                <label>
                  API key mới
                  <input
                    type="password"
                    autoComplete="new-password"
                    value={key}
                    minLength={10}
                    maxLength={4096}
                    required
                    onChange={(e) => setKey(e.target.value)}
                  />
                </label>
                <div className="ai-actions">
                  <button
                    className="secondary-button"
                    type="submit"
                    disabled={busy || !connection || !options?.credentialStorageReady}
                  >
                    Lưu key
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={busy || !connection?.version || !connection.configured}
                    onClick={() => void change(true)}
                  >
                    Gỡ key
                  </button>
                </div>
              </form>
            </>
          )}
        </div>
        <div className="ai-oauth-status">
          <p>
            <strong>OpenCode Free</strong>: chưa khả dụng; đang chờ xác minh kết nối và điều kiện
            sử dụng cho website dùng chung.
          </p>
          <p><strong>ChatGPT Plus/Pro qua OpenCode</strong></p>
          {!chatgptAvailable ? <p>Chưa bật OAuth trong môi trường này.</p> : !profile ? (
            <p>Đăng nhập tài khoản dự án để kết nối ChatGPT.</p>
          ) : (
            <>
              <p>{chatgpt.connected ? "Đã kết nối cho phiên local." : chatgpt.pending ? "Đang chờ đăng nhập ChatGPT." : "Chưa kết nối."}</p>
              {chatgpt.instructions && <p>{chatgpt.instructions}</p>}
              {chatgpt.url && <p><a href={chatgpt.url} target="_blank" rel="noreferrer noopener">Mở trang đăng nhập OpenAI</a></p>}
              <div className="ai-actions">
                {!chatgpt.pending && !chatgpt.connected && <button className="secondary-button" disabled={busy} onClick={() => void chatgptAction("start")}>Kết nối ChatGPT Plus/Pro</button>}
                {chatgpt.pending && chatgpt.url && <button className="secondary-button" disabled={busy} onClick={() => void chatgptAction("finish")}>Tôi đã đăng nhập</button>}
                {chatgpt.connected && choice.credential_source !== "chatgpt" && <button className="secondary-button" disabled={busy} onClick={() => setChoice({...choice, provider: "openai", engine: "opencode", credential_source: "chatgpt", retrieval_mode: "keyword", model: "gpt-5.6-luna"})}>Sử dụng ChatGPT đã kết nối</button>}
                {(chatgpt.pending || chatgpt.connected) && <button className="secondary-button" disabled={busy} onClick={() => void chatgptAction("disconnect")}>Ngắt kết nối</button>}
              </div>
              <p className="small-print">Phiên thử nghiệm local hết hạn sau khoảng một giờ hoặc khi backend khởi động lại.</p>
            </>
          )}
          <p>
            <strong>Claude Pro OAuth</strong>: nhà cung cấp không hỗ trợ đăng nhập Pro cho ứng dụng
            bên ngoài gọi model.
          </p>
          <p className="small-print">
            API key được mã hóa trên server và không hiển thị lại. Chi phí API theo tài khoản sở hữu
            key, không tự động trừ vào gói Plus/Pro. Các yêu cầu gặp lỗi key không tự chuyển sang
            key khác.
          </p>
        </div>
      </section>
    </>
  );
}
