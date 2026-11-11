import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Role, User } from "../api/types";
import { ErrorBox } from "../components/bits";
import { homeFor, useAuth } from "../auth/AuthContext";

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const state = (useLocation().state ?? {}) as { next?: string; role?: Role };
  const [role, setRole] = useState<Role>(state.role ?? "patient");
  const [phone, setPhone] = useState("+91 ");
  const [otp, setOtp] = useState("");
  const [sent, setSent] = useState(false);
  const [wait, setWait] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (wait <= 0) return;
    const id = setTimeout(() => setWait(wait - 1), 1000);
    return () => clearTimeout(id);
  }, [wait]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError(null);
    try { await fn(); } catch (e) { setError(e); } finally { setBusy(false); }
  };

  const requestOtp = (e?: FormEvent) => {
    e?.preventDefault();
    return run(async () => {
      const r = await api<{ retry_after_seconds: number }>("/auth/otp/request", { method: "POST", body: { phone, role }, auth: false });
      setSent(true); setWait(r.retry_after_seconds);
    });
  };

  const verify = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => {
      const r = await api<{ access: string; user: User }>("/auth/otp/verify", { method: "POST", body: { phone, role, otp }, auth: false });
      signIn(r.user, r.access);
      navigate(state.next && r.user.role === "patient" ? state.next : homeFor(r.user), { replace: true });
    });
  };

  return (
    <div className="wrap">
      <div className="card narrow">
        <h1>Log in</h1>
        <div className="row" style={{ justifyContent: "center", margin: "14px 0" }} role="group" aria-label="I am a">
          {(["patient", "doctor"] as const).map((r) => (
            <button key={r} type="button" className={role === r ? "primary" : ""} disabled={sent} onClick={() => setRole(r)}>
              {r === "patient" ? "Patient" : "Doctor"}
            </button>
          ))}
        </div>
        {!sent ? (
          <form onSubmit={requestOtp} className="row" style={{ flexDirection: "column", alignItems: "stretch" }}>
            <label>Mobile number<input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" /></label>
            <ErrorBox error={error} />
            <button className="primary block" disabled={busy}>Send OTP</button>
          </form>
        ) : (
          <form onSubmit={verify} className="row" style={{ flexDirection: "column", alignItems: "stretch" }}>
            <label>Enter 6-digit OTP
              <input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric"
                autoComplete="one-time-code" placeholder="------" autoFocus />
            </label>
            <ErrorBox error={error} />
            <button className="primary block" disabled={busy || otp.length !== 6}>Verify and continue</button>
            <p className="muted center">
              {wait > 0 ? `Resend OTP in 0:${String(wait).padStart(2, "0")}` : <button type="button" className="link" onClick={() => requestOtp()}>Resend OTP</button>}
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
