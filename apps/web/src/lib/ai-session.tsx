"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type Profile = { id: string; email?: string; displayName: string; role: "user" | "admin" };
export type AiChoice = {
  engine: "direct" | "opencode";
  provider: "openai" | "anthropic" | "deepseek" | "openrouter";
  credential_source: "auto" | "personal" | "shared" | "chatgpt";
  model: string;
  retrieval_mode: "hybrid" | "keyword";
};
export type SessionInfo = {
  id: string;
  createdAt: string;
  expiresAt: string;
  current: boolean;
  active: boolean;
};
type SessionResponse = { user: Profile; csrfToken: string };
type Session = {
  profile: Profile | null;
  restoring: boolean;
  choice: AiChoice;
  setChoice: (value: AiChoice) => void;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (displayName: string, email: string, password: string) => Promise<void>;
  signInGoogle: (credential: string) => Promise<void>;
  signOut: () => Promise<void>;
  signOutAll: () => Promise<void>;
  request: <T>(path: string, init?: RequestInit) => Promise<T>;
};
const Context = createContext<Session | null>(null);
const defaults: AiChoice = {
  engine: "direct",
  provider: "openai",
  credential_source: "auto",
  model: "",
  retrieval_mode: "hybrid",
};

async function backend<T>(path: string, init: RequestInit = {}, csrf = ""): Promise<T> {
  const origin = new URL(process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000");
  if (origin.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(origin.hostname)) {
    throw new Error("Kết nối backend cần sử dụng HTTPS.");
  }
  // The two loopback spellings are different cookie sites in browsers.
  if (
    typeof window !== "undefined" &&
    ["localhost", "127.0.0.1"].includes(origin.hostname) &&
    ["localhost", "127.0.0.1"].includes(window.location.hostname)
  ) {
    origin.hostname = window.location.hostname;
  }
  const headers = new Headers(init.headers);
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const response = await fetch(`${origin.origin}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
    redirect: "error",
    signal: init.signal || AbortSignal.timeout(90000),
  });
  if (response.status === 204) return undefined as T;
  let result: { error?: { code?: string; message?: string } } & T;
  try {
    result = await response.json();
  } catch {
    throw new Error("Không nhận được phản hồi hợp lệ từ backend.");
  }
  if (!response.ok) {
    const messages: Record<string, string> = {
      invalid_credentials: "Email hoặc mật khẩu không đúng.",
      account_exists: "Email đã có tài khoản. Hãy đăng nhập.",
      account_link_required: "Email đã có tài khoản. Đăng nhập bằng mật khẩu rồi liên kết Google.",
      account_disabled: "Tài khoản đang bị khóa.",
      google_unavailable: "Đăng nhập Google chưa được cấu hình.",
      invalid_google_token: "Không xác minh được tài khoản Google. Hãy thử lại.",
      csrf_failed: "Phiên đã thay đổi. Hãy tải lại trang và thử lại.",
      ai_authentication_failed: "Nhà cung cấp từ chối API key đã chọn.",
      ai_rate_limited: "Đã đạt giới hạn sử dụng hoặc engine đang bận. Hãy thử lại sau.",
      opencode_unavailable: "OpenCode chưa được bật hoặc cấu hình cho môi trường này.",
      oauth_exists: "Đã có phiên ChatGPT. Hãy ngắt kết nối trước khi tạo phiên mới.",
    };
    throw new Error(
      messages[result.error?.code || ""] || result.error?.message || "Yêu cầu chưa thực hiện được.",
    );
  }
  return result;
}

export function AiSessionProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [choice, setChoice] = useState<AiChoice>(defaults);
  const csrf = useRef("");
  const generation = useRef(0);

  const accept = useCallback((result: SessionResponse, attempt: number) => {
    if (attempt !== generation.current) throw new Error("Phiên đã thay đổi.");
    csrf.current = result.csrfToken;
    setProfile(result.user);
  }, []);

  useEffect(() => {
    let active = true;
    const attempt = generation.current;
    backend<SessionResponse>("/api/v1/auth/me", { signal: AbortSignal.timeout(5000) })
      .then((result) => {
        if (active) accept(result, attempt);
      })
      .catch(() => {
        /* No session or backend unavailable; user can sign in. */
      })
      .finally(() => {
        if (active) setRestoring(false);
      });
    return () => {
      active = false;
    };
  }, [accept]);

  useEffect(() => {
    if (!profile) return;
    let active = true;
    const attempt = generation.current;
    backend<{connected: boolean}>("/api/v1/ai/chatgpt", { signal: AbortSignal.timeout(5000) })
      .then((result) => {
        if (active && attempt === generation.current && result.connected) {
          setChoice((current) => current === defaults ? {
            engine: "opencode", provider: "openai", credential_source: "chatgpt",
            model: "gpt-5.6-luna", retrieval_mode: "keyword",
          } : current);
        }
      })
      .catch(() => { /* OAuth is optional and may be disabled. */ });
    return () => { active = false; };
  }, [profile]);

  const request = useCallback(async <T,>(path: string, init?: RequestInit) => {
    const attempt = generation.current;
    const result = await backend<T>(path, init, csrf.current);
    if (attempt !== generation.current) throw new Error("Phiên đã thay đổi.");
    return result;
  }, []);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const attempt = ++generation.current;
      const result = await backend<SessionResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      accept(result, attempt);
    },
    [accept],
  );

  const signUp = useCallback(
    async (displayName: string, email: string, password: string) => {
      const attempt = ++generation.current;
      const result = await backend<SessionResponse>("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({ displayName, email, password }),
      });
      accept(result, attempt);
    },
    [accept],
  );

  const signInGoogle = useCallback(
    async (credential: string) => {
      const attempt = ++generation.current;
      const result = await backend<SessionResponse>(
        "/api/v1/auth/google",
        {
          method: "POST",
          body: JSON.stringify({ credential }),
        },
        csrf.current,
      );
      accept(result, attempt);
    },
    [accept],
  );

  const endSession = useCallback(async (all: boolean) => {
    const attempt = generation.current;
    await backend<void>(
      all ? "/api/v1/auth/logout-all" : "/api/v1/auth/logout",
      {
        method: "POST",
        body: "{}",
      },
      csrf.current,
    );
    if (attempt !== generation.current) throw new Error("Phiên đã thay đổi.");
    generation.current += 1;
    csrf.current = "";
    setProfile(null);
    setChoice(defaults);
  }, []);

  const signOut = useCallback(() => endSession(false), [endSession]);
  const signOutAll = useCallback(() => endSession(true), [endSession]);
  return (
    <Context.Provider
      value={{
        profile,
        restoring,
        choice,
        setChoice,
        signIn,
        signUp,
        signInGoogle,
        signOut,
        signOutAll,
        request,
      }}
    >
      {children}
    </Context.Provider>
  );
}

export function useAiSession() {
  const session = useContext(Context);
  if (!session) throw new Error("AI session provider is missing");
  return session;
}
