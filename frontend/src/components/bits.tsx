import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { initials } from "../lib/format";

export const Avatar = ({ name, small }: { name: string; small?: boolean }) =>
  <div className={`avatar${small ? " sm" : ""}`} aria-hidden="true">{initials(name)}</div>;

export const Verified = () => <span className="pill">✓ Verified</span>;

export function Loading() { return <div className="wrap"><p className="muted">Loading…</p></div>; }

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="alert" role="alert">{error instanceof ApiError ? error.message : "Something went wrong. Try again."}</div>;
}

export function Steps({ current }: { current: 1 | 2 | 3 }) {
  const step = (n: number, label: string) => <span className="steps"><i className={n <= current ? "" : "off"}>{n}</i> {label}</span>;
  return <div className="steps">{step(1, "Slot")}<hr />{step(2, "Details")}<hr />{step(3, "Payment")}</div>;
}

export function NotFound({ children }: { children?: ReactNode }) {
  return <div className="wrap"><div className="card center"><h2>{children ?? "Page not found"}</h2><Link to="/">Back to home</Link></div></div>;
}

/** Route guard content: tells a visitor why they cannot see a page and where to go. */
export function NeedLogin({ role, next }: { role: "patient" | "doctor"; next: string }) {
  return (
    <div className="wrap"><div className="card narrow center">
      <h2>Log in as a {role}</h2>
      <p className="muted" style={{ marginBottom: 14 }}>This page is for {role}s.</p>
      <Link to="/login" state={{ next, role }} className="btn primary">Log in</Link>
    </div></div>
  );
}
