import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, refreshAccess, setAccessToken, setSessionLostHandler } from "../api/client";
import type { User } from "../api/types";

interface Auth {
  user: User | null;
  loading: boolean;
  signIn: (user: User, access: string) => void;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
}
const Ctx = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setSessionLostHandler(() => setUser(null));
    // Boot: the refresh cookie (if any) gives us a session. A 401 just means anonymous.
    refreshAccess()
      .then((token) => (token ? api<User>("/me") : null))
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const signIn = useCallback((u: User, access: string) => { setAccessToken(access); setUser(u); }, []);
  const signOut = useCallback(async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    setAccessToken(null);
    setUser(null);
  }, []);
  const refreshUser = useCallback(async () => setUser(await api<User>("/me")), []);

  const value = useMemo(() => ({ user, loading, signIn, signOut, refreshUser }), [user, loading, signIn, signOut, refreshUser]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): Auth {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}

/** Where a signed-in user belongs by default (doctor routing follows the contract's status table). */
export function homeFor(user: User): string {
  if (user.role === "patient") return "/";
  const status = user.doctor?.verification_status ?? "draft";
  return status === "approved" || status === "suspended" ? "/doctor/schedule" : "/doctor/onboarding";
}
