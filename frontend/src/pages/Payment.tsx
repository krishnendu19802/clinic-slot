import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useBooking, usePolicy } from "../api/queries";
import type { Booking, PayOrder } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import BookingSummary from "../components/BookingSummary";
import { ErrorBox, Loading, NeedLogin, NotFound, Steps } from "../components/bits";
import { rupees } from "../lib/format";
import { useCountdown } from "../lib/useCountdown";
import { HoldGone } from "./Details";

// DEV: the backend gateway is a stub, so this page fakes the Razorpay Checkout step.
// Real integration: open window.Razorpay with the PayOrder, then call verify from its handler.
const DEV_CHECKOUT = import.meta.env.VITE_RAZORPAY_DEV !== "false";
const METHODS = ["UPI", "Card", "Netbanking", "Wallet"];

/** After a verify that errored or timed out the webhook may still confirm: poll for ~30 s. */
async function pollConfirmed(id: string): Promise<boolean> {
  for (let i = 0; i < 15; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    try { if ((await api<Booking>(`/bookings/${id}`)).status === "confirmed") return true; } catch { /* keep polling */ }
  }
  return false;
}

export default function Payment() {
  const { id = "" } = useParams();
  const { user, loading } = useAuth();
  const { data: booking, error: loadError } = useBooking(id);
  const { data: policy } = usePolicy();
  const left = useCountdown(booking?.hold_expires_at, booking?.server_time);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [method, setMethod] = useState("UPI");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const [lost, setLost] = useState(false);

  if (loading) return <Loading />;
  if (!user) return <NeedLogin role="patient" next={`/book/${id}/payment`} />;
  if (loadError instanceof ApiError && loadError.status === 404) return <NotFound>Booking not found</NotFound>;
  if (!booking) return <Loading />;
  if (booking.status === "confirmed") return <Navigate to={`/book/${id}/confirmed`} replace />;
  if (lost) return <HoldGone doctorId={booking.doctor.id} message="That slot was taken before your payment completed. You will be refunded." />;
  if (booking.status !== "pending_payment") return <HoldGone doctorId={booking.doctor.id} message="This booking is no longer active" />;
  if (!booking.patient) return <Navigate to={`/book/${id}/details`} replace />;
  if (left === 0 || (error instanceof ApiError && error.code === "HOLD_EXPIRED")) return <HoldGone doctorId={booking.doctor.id} />;

  const pay = async () => {
    setBusy(true); setError(null);
    try {
      const order = await api<PayOrder>(`/bookings/${id}/pay`, { method: "POST" });
      const verifyBody = DEV_CHECKOUT
        ? { razorpay_order_id: order.razorpay_order_id, razorpay_payment_id: `pay_dev_${Date.now()}`, razorpay_signature: "dev" }
        : null;
      if (!verifyBody) throw new Error("Razorpay Checkout is not wired yet");
      try {
        await api(`/bookings/${id}/payment/verify`, { method: "POST", body: verifyBody });
      } catch (e) {
        if (e instanceof ApiError && e.status < 500) throw e; // a real answer: show it
        setPending(true);
        if (!(await pollConfirmed(id))) return; // webhook never arrived within 30 s: told "we'll confirm by SMS"
      }
      qc.invalidateQueries({ queryKey: ["holds"] });
      navigate(`/book/${id}/confirmed`, { replace: true });
    } catch (e) {
      if (e instanceof ApiError && e.code === "SLOT_LOST_REFUNDED") setLost(true); else setError(e);
    } finally { setBusy(false); }
  };

  return (
    <div className="wrap">
      <Steps current={3} />
      <div className="row top">
        <div className="card grow" style={{ flex: 1.3, minWidth: 320, display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2 style={{ margin: 0 }}>Pay {rupees(booking.fee_paise)}</h2>
            <span className="pill amber">Test mode</span>
          </div>
          <p className="muted">Generic checkout placeholder. The real build opens Razorpay Checkout here.</p>
          <div className="row" role="radiogroup" aria-label="Payment method">
            {METHODS.map((m) => (
              <button key={m} type="button" role="radio" aria-checked={method === m} className={`slot${method === m ? " on" : ""}`} onClick={() => setMethod(m)}>{m}</button>
            ))}
          </div>
          {method === "UPI" && <label>UPI ID<input placeholder="name@bank" /></label>}
          {policy && <p className="alert info">{policy.text}</p>}
          {pending && <p className="alert info" role="status">Confirming your payment… this can take up to 30 seconds. If it does not finish, we will confirm by SMS.</p>}
          <ErrorBox error={error} />
          <button className="primary block" onClick={pay} disabled={busy}>{busy ? "Processing…" : `Pay ${rupees(booking.fee_paise)} securely`}</button>
          <p className="muted center">Your slot is confirmed only after payment is verified.</p>
          <Link to={`/doctors/${booking.doctor.id}`} className="center">Choose a different slot</Link>
        </div>
        <div style={{ flex: 0.8, minWidth: 280 }}><BookingSummary booking={booking} left={left} /></div>
      </div>
    </div>
  );
}
