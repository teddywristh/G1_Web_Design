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
export type AskEvent =
  | { type: "stage"; stage: string }
  | { type: "sources"; items: { title: string; article?: string | null; clause?: string | null }[] }
  | { type: "claim"; text: string; citations: unknown[] }
  | { type: "reset" }
  | { type: "done"; response: unknown }
  | { type: "error"; code: string; message: string; status: number };
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
  // POST and receive the answer as server-sent events; resolves with the final response.
  stream: <T>(path: string, init: RequestInit, onEvent: (event: AskEvent) => void) => Promise<T>;
};
const Context = createContext<Session | null>(null);
const defaults: AiChoice = {
  engine: "direct",
  provider: "openai",
  credential_source: "auto",
  model: "",
  retrieval_mode: "hybrid",
};

const ERROR_MESSAGES: Record<string, string> = {
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

export class HttpError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

function endpoint(path: string): string {
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
  return `${origin.origin}${path}`;
}

function explain(code: string | undefined, message: string | undefined): string {
  return ERROR_MESSAGES[code || ""] || message || "Yêu cầu chưa thực hiện được.";
}

async function backend<T>(path: string, init: RequestInit = {}, csrf = ""): Promise<T> {
  const headers = new Headers(init.headers);
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const response = await fetch(endpoint(path), {
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
  if (!response.ok) throw new HttpError(explain(result.error?.code, result.error?.message), response.status);
  return result;
}

// Server-sent events over fetch (EventSource cannot POST). Blocks end with a blank line.
async function streamBackend<T>(
  path: string,
  init: RequestInit,
  csrf: string,
  onEvent: (event: AskEvent) => void,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const response = await fetch(endpoint(path), {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
    redirect: "error",
    signal: init.signal || AbortSignal.timeout(120000),
  });
  if (!response.ok || !response.body) {
    let error: { code?: string; message?: string } | undefined;
    try {
      error = (await response.json()).error;
    } catch {
      /* Not JSON. */
    }
    throw new HttpError(explain(error?.code, error?.message), response.status);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let final: T | undefined;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    // Normalise the whole buffer: a chunk may split "\r" from "\n".
    buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, "\n");
    let end: number;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (!data) continue; // keep-alive comment
      let event: AskEvent;
      try {
        event = JSON.parse(data);
      } catch {
        continue;
      }
      if (event.type === "error") throw new HttpError(explain(event.code, event.message), event.status);
      if (event.type === "done") final = event.response as T;
      onEvent(event);
    }
  }
  if (final === undefined) throw new Error("Kết nối bị ngắt trước khi nhận đủ câu trả lời.");
  return final;
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

  const stream = useCallback(
    async <T,>(path: string, init: RequestInit, onEvent: (event: AskEvent) => void) => {
      const attempt = generation.current;
      const result = await streamBackend<T>(path, init, csrf.current, onEvent);
      if (attempt !== generation.current) throw new Error("Phiên đã thay đổi.");
      return result;
    },
    [],
  );

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
        stream,
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
