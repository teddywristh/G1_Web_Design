"use client";

import { useCallback, useEffect, useState } from "react";
import { useAiSession, type SessionInfo } from "@/lib/ai-session";

type Page = { items: SessionInfo[]; nextCursor: string | null };

export function AccountSessions() {
  const { request, signOutAll } = useAiSession();
  const [page, setPage] = useState<Page | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(
    async (cursor?: string) => {
      const next = await request<Page>(
        `/api/v1/auth/sessions${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
      );
      setPage((current) =>
        cursor && current
          ? { items: [...current.items, ...next.items], nextCursor: next.nextCursor }
          : next,
      );
    },
    [request],
  );

  useEffect(() => {
    let active = true;
    request<Page>("/api/v1/auth/sessions")
      .then((value) => {
        if (active) setPage(value);
      })
      .catch(() => {
        if (active) setError("Không tải được danh sách phiên.");
      });
    return () => {
      active = false;
    };
  }, [request]);

  async function revoke(id: string) {
    setBusy(true);
    setError("");
    try {
      await request(`/api/v1/auth/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không thu hồi được phiên.");
    } finally {
      setBusy(false);
    }
  }

  async function endAll() {
    setBusy(true);
    setError("");
    try {
      await signOutAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không đăng xuất được.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="account-sessions">
      <h3>Phiên đăng nhập</h3>
      {!page && !error && <p>Đang tải phiên…</p>}
      {page && (
        <ul>
          {page.items.map((item) => (
            <li key={item.id}>
              <div>
                <strong>{item.current ? "Thiết bị này" : "Phiên khác"}</strong>
                <small>
                  {item.active
                    ? `Hết hạn ${new Date(item.expiresAt).toLocaleString("vi-VN")}`
                    : "Đã hết hạn hoặc thu hồi"}
                </small>
              </div>
              {!item.current && item.active && (
                <button
                  type="button"
                  className="secondary-button"
                  disabled={busy}
                  onClick={() => void revoke(item.id)}
                >
                  Thu hồi
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {page?.nextCursor && (
        <button
          type="button"
          className="secondary-button"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void load(page.nextCursor!)
              .catch(() => setError("Không tải được phiên tiếp theo."))
              .finally(() => setBusy(false));
          }}
        >
          Tải thêm
        </button>
      )}
      <button
        type="button"
        className="secondary-button"
        disabled={busy}
        onClick={() => void endAll()}
      >
        Đăng xuất tất cả phiên
      </button>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
