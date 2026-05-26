import { useState } from "react";
import type React from "react";
import type { InventorySyncController } from "../lib/inventorySync";

export function AuthPanel({ sync }: { sync: InventorySyncController }) {
  const [email, setEmail] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!email.trim()) return;
    await sync.signInWithEmail(email.trim());
  }

  if (!sync.configured) {
    return (
      <section data-testid="auth-panel" className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Đồng bộ kho cá nhân</h2>
            <p className="text-sm text-slate-600">Đang lưu cục bộ vì chưa cấu hình Supabase.</p>
          </div>
          <span className="rounded-full border border-slate-200 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
            Chỉ lưu trên thiết bị
          </span>
        </div>
        <p className="mt-3 text-xs text-slate-500">Chưa cấu hình: {sync.missingConfig.join(", ")}</p>
      </section>
    );
  }

  return (
    <section data-testid="auth-panel" className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Đồng bộ kho cá nhân</h2>
          <p className="text-sm text-slate-600">Supabase chỉ lưu mã máy ảnh và mã pin trong kho của bạn.</p>
          {sync.user ? (
            <p data-testid="auth-user" className="mt-2 text-sm font-medium text-slate-900">
              Đã đăng nhập: {sync.user.email ?? sync.user.id}
            </p>
          ) : null}
        </div>

        {sync.user ? (
          <button
            data-testid="auth-sign-out"
            className="min-h-10 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            type="button"
            onClick={() => {
              sync.signOut();
            }}
            disabled={sync.authLoading}
          >
            Đăng xuất
          </button>
        ) : (
          <form className="flex w-full flex-col gap-2 sm:w-auto sm:min-w-[360px] sm:flex-row" onSubmit={submit}>
            <input
              data-testid="auth-email"
              className="min-h-10 flex-1 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
              type="email"
              placeholder="email@example.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <button
              data-testid="auth-send-link"
              className="min-h-10 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
              type="submit"
              disabled={sync.authLoading || !email.trim()}
            >
              Gửi liên kết đăng nhập
            </button>
          </form>
        )}
      </div>

      {sync.authMessage ? (
        <div data-testid="auth-message" className="mt-3 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-800">
          {sync.authMessage}
        </div>
      ) : null}
    </section>
  );
}
