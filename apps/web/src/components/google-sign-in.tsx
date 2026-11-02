"use client";

import { useEffect, useRef, useState } from "react";
import { useAiSession } from "@/lib/ai-session";

type GoogleIdentity = {
  accounts: {
    id: {
      initialize: (config: {
        client_id: string;
        callback: (result: { credential: string }) => void;
        auto_select: boolean;
        nonce: string;
      }) => void;
      renderButton: (element: HTMLElement, options: Record<string, unknown>) => void;
    };
  };
};
declare global {
  interface Window {
    google?: GoogleIdentity;
  }
}

export function GoogleSignIn({
  onCredential,
  disabled,
}: {
  onCredential: (credential: string) => void;
  disabled: boolean;
}) {
  const { request } = useAiSession();
  const mount = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  callback.current = onCredential;
  const [error, setError] = useState("");
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID;

  useEffect(() => {
    if (!clientId || disabled) return;
    let active = true;
    let nonce = "";
    function render() {
      if (!active || !mount.current || !window.google || !nonce) return;
      mount.current.replaceChildren();
      window.google.accounts.id.initialize({
        client_id: clientId!,
        auto_select: false,
        nonce,
        callback: (response) => {
          if (active && response.credential) callback.current(response.credential);
        },
      });
      window.google.accounts.id.renderButton(mount.current, {
        type: "standard",
        theme: "outline",
        size: "large",
        text: "continue_with",
        locale: "vi",
        shape: "rectangular",
      });
    }
    let script = document.querySelector<HTMLScriptElement>("script[data-google-identity]");
    if (!script) {
      script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.dataset.googleIdentity = "true";
      document.head.appendChild(script);
    }
    const failed = () => {
      if (active) setError("Không tải được đăng nhập Google.");
    };
    script.addEventListener("load", render);
    script.addEventListener("error", failed);
    request<{ nonce: string }>("/api/v1/auth/google/challenge")
      .then((value) => {
        if (active) {
          nonce = value.nonce;
          render();
        }
      })
      .catch(() => {
        if (active) setError("Đăng nhập Google chưa được cấu hình trên server.");
      });
    return () => {
      active = false;
      script?.removeEventListener("load", render);
      script?.removeEventListener("error", failed);
    };
  }, [clientId, disabled, request]);

  if (!clientId)
    return (
      <>
        <button type="button" disabled>
          Tiếp tục với Google
        </button>
        <p className="small-print">Đăng nhập Google chưa được cấu hình.</p>
      </>
    );
  if (disabled) return <p className="small-print">Đang xử lý đăng nhập Google…</p>;
  return (
    <div aria-label="Đăng nhập Google">
      {error && <p role="status">{error}</p>}
      <div ref={mount} />
    </div>
  );
}
