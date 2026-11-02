"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

export type Profile = { id: string; email?: string; displayName: string; role: "user" | "admin" };
export type AiChoice = {
  provider: "openai" | "anthropic";
  credential_source: "auto" | "personal" | "shared";
  model: string;
  retrieval_mode: "hybrid" | "keyword";
};
type Tokens = { idToken: string; refreshToken: string; expiresAt: number };
type Session = {
  profile: Profile | null;
  choice: AiChoice;
  setChoice: (value: AiChoice) => void;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
  request: <T>(path: string, init?: RequestInit) => Promise<T>;
};
const Context = createContext<Session | null>(null);
const defaults: AiChoice = {
  provider: "openai",
  credential_source: "auto",
  model: "",
  retrieval_mode: "hybrid",
};

function firebaseEndpoint(service: "identitytoolkit" | "securetoken", path: string) {
  const key = process.env.NEXT_PUBLIC_FIREBASE_API_KEY;
  if (!key) throw new Error("Chưa cấu hình đăng nhập cho website.");
  const emulator = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_URL;
  let origin = `https://${service}.googleapis.com`;
  if (emulator) {
    const url = new URL(emulator);
    if (
      process.env.NEXT_PUBLIC_APP_ENV === "production" ||
      !["localhost", "127.0.0.1"].includes(url.hostname)
    ) {
      throw new Error("Cấu hình đăng nhập không hợp lệ.");
    }
    origin = `${url.origin}/${service}.googleapis.com`;
  }
  return `${origin}/v1/${path}?key=${encodeURIComponent(key)}`;
}

async function backend<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  const origin = new URL(process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000");
  if (origin.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(origin.hostname)) {
    throw new Error("Kết nối backend cần sử dụng HTTPS.");
  }
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`${origin.origin}${path}`, {
    ...init,
    headers,
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
    signal: init.signal || AbortSignal.timeout(90000),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error?.message || "Yêu cầu chưa thực hiện được.");
  return result as T;
}

export function AiSessionProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [choice, setChoice] = useState<AiChoice>(defaults);
  const tokens = useRef<Tokens | null>(null);
  const generation = useRef(0);
  const refreshing = useRef<Promise<string> | null>(null);

  const signOut = useCallback(() => {
    generation.current += 1;
    tokens.current = null;
    refreshing.current = null;
    setProfile(null);
    setChoice(defaults);
  }, []);

  const signIn = useCallback(
    async (email: string, password: string) => {
      signOut();
      const attempt = generation.current;
      const response = await fetch(
        firebaseEndpoint("identitytoolkit", "accounts:signInWithPassword"),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
          body: JSON.stringify({ email, password, returnSecureToken: true }),
          signal: AbortSignal.timeout(15000),
          redirect: "error",
        },
      );
      if (!response.ok) throw new Error("Không đăng nhập được. Kiểm tra tài khoản và mật khẩu.");
      const data = await response.json();
      const user = await backend<Profile>(data.idToken, "/api/v1/users/me/bootstrap", {
        method: "POST",
      });
      if (attempt !== generation.current) throw new Error("Phiên đăng nhập đã thay đổi.");
      tokens.current = {
        idToken: data.idToken,
        refreshToken: data.refreshToken,
        expiresAt: Date.now() + Number(data.expiresIn) * 1000,
      };
      setProfile(user);
    },
    [signOut],
  );

  const token = useCallback(async () => {
    const saved = tokens.current;
    if (!saved) throw new Error("Đăng nhập trong Thiết lập để kết nối AI.");
    if (saved.expiresAt > Date.now() + 60000) return saved.idToken;
    if (refreshing.current) return refreshing.current;
    const attempt = generation.current;
    const operation = (async () => {
      const response = await fetch(firebaseEndpoint("securetoken", "token"), {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type: "refresh_token",
          refresh_token: saved.refreshToken,
        }),
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.timeout(15000),
      });
      if (!response.ok) throw new Error("Phiên đã hết hạn. Vui lòng đăng nhập lại.");
      const data = await response.json();
      if (attempt !== generation.current) throw new Error("Phiên đã thay đổi.");
      tokens.current = {
        idToken: data.id_token,
        refreshToken: data.refresh_token,
        expiresAt: Date.now() + Number(data.expires_in) * 1000,
      };
      return data.id_token as string;
    })();
    refreshing.current = operation;
    try {
      return await operation;
    } catch (error) {
      if (attempt === generation.current) signOut();
      throw error;
    } finally {
      if (refreshing.current === operation) refreshing.current = null;
    }
  }, [signOut]);

  const request = useCallback(
    async <T,>(path: string, init?: RequestInit) => {
      const attempt = generation.current;
      const result = await backend<T>(await token(), path, init);
      if (attempt !== generation.current) throw new Error("Phiên đã thay đổi.");
      return result;
    },
    [token],
  );

  return (
    <Context.Provider value={{ profile, choice, setChoice, signIn, signOut, request }}>
      {children}
    </Context.Provider>
  );
}

export function useAiSession() {
  const session = useContext(Context);
  if (!session) throw new Error("AI session provider is missing");
  return session;
}
