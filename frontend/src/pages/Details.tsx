import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useBooking } from "../api/queries";
import type { PatientDetails } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import BookingSummary from "../components/BookingSummary";
import { ErrorBox, Loading, NeedLogin, NotFound, Steps } from "../components/bits";
import { useCountdown } from "../lib/useCountdown";

export function HoldGone({ doctorId, message }: { doctorId?: number; message?: string }) {
  return (
    <div className="wrap"><div className="card narrow center">
      <h2>{message ?? "Your hold on this slot has expired"}</h2>
      <p className="muted" style={{ marginBottom: 14 }}>Slots are held for a few minutes while you check out.</p>
      <Link className="btn primary" to={doctorId ? `/doctors/${doctorId}` : "/doctors"}>Choose another slot</Link>
    </div></div>
  );
}

export default function Details() {
  const { id } = useParams();
  const { user, loading } = useAuth();
  const { data: booking, error: loadError } = useBooking(id);
  const left = useCountdown(booking?.hold_expires_at, booking?.server_time);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [form, setForm] = useState<PatientDetails>({ is_self: true, name: "", age: 0, gender: "male", phone: "", reason: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (booking?.patient) setForm(booking.patient);
    else if (user) setForm((f) => ({ ...f, name: user.name, phone: user.phone }));
  }, [booking?.patient, user]);

  if (loading) return <Loading />;
  if (!user) return <NeedLogin role="patient" next={`/book/${id}/details`} />;
  if (loadError instanceof ApiError && loadError.status === 404) return <NotFound>Booking not found</NotFound>;
  if (!booking) return <Loading />;
  if (booking.status === "confirmed") return <Navigate to={`/book/${id}/confirmed`} replace />;
  if (booking.status !== "pending_payment") return <HoldGone doctorId={booking.doctor.id} message="This booking is no longer active" />;
  if (left === 0 || (error instanceof ApiError && error.code === "HOLD_EXPIRED")) return <HoldGone doctorId={booking.doctor.id} />;

  const set = <K extends keyof PatientDetails>(k: K, v: PatientDetails[K]) => setForm((f) => ({ ...f, [k]: v }));
  const who = (self: boolean) => setForm((f) => ({ ...f, is_self: self, name: self ? user.name : "", phone: self ? user.phone : f.phone }));

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      await api(`/bookings/${id}`, { method: "PATCH", body: { patient: form } });
      await qc.invalidateQueries({ queryKey: ["booking", id] });
      qc.invalidateQueries({ queryKey: ["holds"] });
      navigate(`/book/${id}/payment`);
    } catch (err) { setError(err); } finally { setBusy(false); }
  };
  const fieldErrors = (error instanceof ApiError ? error.fields.patient : undefined) as Record<string, string[]> | undefined;

  return (
    <div className="wrap">
      <Steps current={2} />
      <div className="row top">
        <form className="card grow" onSubmit={submit} style={{ flex: 1.3, minWidth: 320, display: "flex", flexDirection: "column", gap: 14 }}>
          <h2>Who is the patient?</h2>
          <div className="row" role="radiogroup" aria-label="Patient">
            {[true, false].map((self) => (
              <label key={String(self)} style={{ flexDirection: "row", alignItems: "center", border: "1.5px solid #e1e5ef", borderRadius: 14, padding: "12px 14px", gap: 10 }}>
                <input type="radio" name="who" checked={form.is_self === self} onChange={() => who(self)} style={{ width: "auto", minHeight: 0 }} />
                {self ? "Myself" : "Family member"}
              </label>
            ))}
          </div>
          <div className="row">
            <label>Full name<input required value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="As on ID" /></label>
            <label>Age<input required type="number" min={0} max={120} value={form.age || ""} onChange={(e) => set("age", Number(e.target.value))} /></label>
          </div>
          <div className="row">
            <label>Gender
              <select value={form.gender} onChange={(e) => set("gender", e.target.value as PatientDetails["gender"])}>
                <option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
              </select>
            </label>
            <label>Phone<input required value={form.phone} onChange={(e) => set("phone", e.target.value)} inputMode="tel" /></label>
          </div>
          <label>Reason for visit (optional)<input value={form.reason} onChange={(e) => set("reason", e.target.value)} placeholder="e.g. skin rash for 2 weeks" /></label>
          {fieldErrors && <div className="alert" role="alert">{Object.entries(fieldErrors).map(([k, v]) => `${k}: ${v.join(", ")}`).join(" · ")}</div>}
          {!fieldErrors && <ErrorBox error={error} />}
          <button className="primary block" disabled={busy}>Continue to payment</button>
        </form>
        <div style={{ flex: 0.8, minWidth: 280 }}><BookingSummary booking={booking} left={left} /></div>
      </div>
    </div>
  );
}
