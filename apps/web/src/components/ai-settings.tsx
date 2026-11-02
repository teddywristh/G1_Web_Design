"use client";

import { useEffect, useState, type FormEvent } from "react";
import { KeyRound, ShieldCheck } from "lucide-react";
import { useAiSession } from "@/lib/ai-session";

type Connection = {
  provider: "openai" | "anthropic";
  scope: "personal" | "shared";
  configured: boolean;
  enabled: boolean;
  version: number;
  origin: string;
};
type Options = { credentialStorageReady: boolean; connections: Connection[] };

export function AiSettings({
  connected,
  onLogin,
  onConnect,
}: {
  connected: boolean | null;
  onLogin: () => void;
  onConnect: () => void;
}) {
  const { profile, choice, setChoice, request, signIn, signOut } = useAiSession();
  const [options, setOptions] = useState<Options | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [key, setKey] = useState("");
  const [scope, setScope] = useState<"personal" | "shared">("personal");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setOptions(null);
    setKey("");
    setScope("personal");
    setMessage("");
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

  const connection = options?.connections.find(
    (item) => item.provider === choice.provider && item.scope === scope,
  );

  async function login(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      await signIn(email, password);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Không đăng nhập được.");
    } finally {
      setPassword("");
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
              <button className="secondary-button" onClick={signOut} disabled={busy}>
                Đăng xuất
              </button>
            </div>
            <p className="small-print">
              Phiên chỉ lưu trong bộ nhớ. Tải lại trang sẽ cần đăng nhập lại.
            </p>
          </>
        ) : (
          <form onSubmit={login} className="ai-form">
            <p>Đăng nhập tài khoản dự án để lưu key cá nhân hoặc quản lý key chung.</p>
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
                autoComplete="current-password"
                value={password}
                required
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <button className="secondary-button" disabled={busy} type="submit">
              {busy ? "Đang đăng nhập…" : "Đăng nhập tài khoản"}
            </button>
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
        <p>Chọn OpenAI hoặc Claude, dùng key cá nhân hay key chung của hệ thống.</p>
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
                  model: "",
                });
                setKey("");
              }}
            >
              <option value="openai">OpenAI API</option>
              <option value="anthropic">Claude API (Anthropic)</option>
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
                })
              }
            >
              <option value="auto">
                Tự động: cá nhân trước, key chung khi chưa có key cá nhân
              </option>
              <option value="personal">Chỉ key cá nhân</option>
              <option value="shared">Chỉ key chung của hệ thống</option>
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
                  : "Nhập ID model Claude được cấp trong Console"
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
              <option value="hybrid">
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
            <strong>ChatGPT Plus OAuth</strong>: chưa khả dụng cho website này; cần quyền tích hợp
            hosted từ OpenAI.
          </p>
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
