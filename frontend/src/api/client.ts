// Fetch wrapper: access token lives in memory only; the refresh token is an httpOnly cookie.
// A 401 triggers exactly one (shared) refresh, then the request is retried once.
const BASE = "/api/v1";
const FETCH_HEADER = { "X-Requested-With": "fetch" };

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields: Record<string, unknown> = {},
    public details: Record<string, any> = {},
  ) {
    super(message);
  }
}

let accessToken: string | null = null;
let refreshing: Promise<string | null> | null = null;
let onSessionLost: () => void = () => {};

export const setAccessToken = (token: string | null) => { accessToken = token; };
export const setSessionLostHandler = (fn: () => void) => { onSessionLost = fn; };

async function toError(res: Response): Promise<ApiError> {
  let body: any = null;
  try { body = await res.json(); } catch { /* empty body */ }
  const e = body?.error;
  return new ApiError(res.status, e?.code ?? "ERROR", e?.message ?? res.statusText, e?.fields, e?.details);
}

/** One refresh at a time: concurrent 401s share the same promise (token rotation breaks parallel refreshes). */
export function refreshAccess(): Promise<string | null> {
  refreshing ??= fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include", headers: FETCH_HEADER })
    .then(async (res) => {
      if (!res.ok) return null;
      accessToken = (await res.json()).access as string;
      return accessToken;
    })
    .catch(() => null)
    .finally(() => { refreshing = null; });
  return refreshing;
}

type Opts = { method?: string; body?: unknown; form?: FormData; params?: Record<string, unknown>; auth?: boolean };

function url(path: string, params?: Record<string, unknown>) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) if (v !== undefined && v !== "" && v !== null) q.set(k, String(v));
  const qs = q.toString();
  return `${BASE}${path}${qs ? `?${qs}` : ""}`;
}

export async function api<T = unknown>(path: string, opts: Opts = {}): Promise<T> {
  const { method = "GET", body, form, params, auth = true } = opts;
  const send = () => {
    const headers: Record<string, string> = { ...FETCH_HEADER };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`;
    return fetch(url(path, params), {
      method, headers, credentials: "include",
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  };
  let res = await send();
  if (res.status === 401 && auth) {
    if (await refreshAccess()) res = await send();
    else { setAccessToken(null); onSessionLost(); }
  }
  if (!res.ok) throw await toError(res);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
