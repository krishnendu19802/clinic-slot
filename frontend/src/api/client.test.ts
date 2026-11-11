import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, setAccessToken } from "./client";

const json = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("api client", () => {
  beforeEach(() => setAccessToken("old"));
  afterEach(() => vi.unstubAllGlobals());

  it("refreshes once on 401, shares the refresh between parallel calls, and retries", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (u: string, init: RequestInit) => {
      calls.push(`${init.method} ${u} ${(init.headers as any).Authorization ?? ""}`);
      if (u.endsWith("/auth/refresh")) return json(200, { access: "new" });
      return (init.headers as any).Authorization === "Bearer new" ? json(200, { ok: true }) : json(401, { error: { code: "TOKEN_EXPIRED", message: "x" } });
    }));
    const [a, b] = await Promise.all([api("/me"), api("/bookings")]);
    expect([a, b]).toEqual([{ ok: true }, { ok: true }]);
    expect(calls.filter((c) => c.includes("/auth/refresh"))).toHaveLength(1);
  });

  it("surfaces the error envelope as ApiError and calls the session-lost handler when refresh fails", async () => {
    const lost = vi.fn();
    const { setSessionLostHandler } = await import("./client");
    setSessionLostHandler(lost);
    vi.stubGlobal("fetch", vi.fn(async (u: string) =>
      u.endsWith("/auth/refresh") ? json(401, { error: { code: "TOKEN_INVALID", message: "no" } })
        : json(401, { error: { code: "TOKEN_INVALID", message: "no" } })));
    await expect(api("/me")).rejects.toBeInstanceOf(ApiError);
    expect(lost).toHaveBeenCalled();
  });

  it("keeps details from a 409 so the UI can act on them", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(409, { error: { code: "SLOT_TAKEN", message: "m", fields: {}, details: { alternatives: [1] } } })));
    const err = (await api("/bookings", { method: "POST", body: {} }).catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("SLOT_TAKEN");
    expect(err.details.alternatives).toEqual([1]);
  });

  it("does not try to refresh public calls", async () => {
    const f = vi.fn(async () => json(401, { error: { code: "X", message: "m" } }));
    vi.stubGlobal("fetch", f);
    await api("/auth/otp/verify", { method: "POST", body: {}, auth: false }).catch(() => {});
    expect(f).toHaveBeenCalledTimes(1);
  });
});
