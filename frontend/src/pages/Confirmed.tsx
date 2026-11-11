import { Link, Navigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useBooking } from "../api/queries";
import { useAuth } from "../auth/AuthContext";
import { Loading, NeedLogin, NotFound } from "../components/bits";
import { dateLong, ics, rupees, time } from "../lib/format";

export default function Confirmed() {
  const { id } = useParams();
  const { user, loading } = useAuth();
  const { data: b, error } = useBooking(id);
  if (loading) return <Loading />;
  if (!user) return <NeedLogin role="patient" next={`/book/${id}/confirmed`} />;
  if (error instanceof ApiError && error.status === 404) return <NotFound>Booking not found</NotFound>;
  if (!b) return <Loading />;
  if (b.status === "pending_payment") return <Navigate to={`/book/${id}/${b.patient ? "payment" : "details"}`} replace />;

  if (b.status === "cancelled") {
    return (
      <div className="wrap"><div className="card narrow center">
        <h2>Booking cancelled</h2>
        <p className="muted">{b.cancel_reason === "slot_lost" ? "The slot was no longer available." : "This booking was cancelled."}</p>
        {b.refund && <p className="alert info" style={{ margin: "12px 0" }}>Refund of {rupees(b.refund.amount_paise)}: {b.refund.status}</p>}
        <Link to={`/doctors/${b.doctor.id}`}>Book another slot</Link>
      </div></div>
    );
  }

  const download = () => {
    const blob = new Blob([ics({ ref: b.ref, start: b.slot.start, end: b.slot.end, doctor: b.doctor.name, clinic: b.clinic.name, address: b.clinic.address })], { type: "text/calendar" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `${b.ref}.ics`; a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="wrap"><div className="card narrow center">
      <div className="ok-badge" aria-hidden="true">✓</div>
      <h1>You're booked</h1>
      <p className="muted" style={{ margin: "6px 0 18px" }}>Confirmation will be sent by SMS, WhatsApp and email.</p>
      <div className="ticket" style={{ textAlign: "left" }}>
        <p className="muted">Your token</p>
        <div className="token">{b.token}</div>
        <hr style={{ border: 0, borderTop: "1px dashed #afc0ff", margin: "14px 0" }} />
        <b>{b.doctor.name}</b>
        <p className="muted">{b.clinic.name}, {b.clinic.address}, {b.clinic.city}</p>
        <p style={{ marginTop: 8 }}>{dateLong(b.slot.start)} · {time(b.slot.start)} to {time(b.slot.end)}</p>
        <p className="muted">Booking ID {b.ref}</p>
      </div>
      <div className="row" style={{ justifyContent: "center", marginTop: 18 }}>
        <a className="btn" href={`https://www.google.com/maps/search/?api=1&query=${b.clinic.lat},${b.clinic.lng}`} target="_blank" rel="noreferrer">Get directions</a>
        <button onClick={download}>Add to calendar</button>
      </div>
      {/* Reschedule / cancel arrive with the refund work on the backend. */}
      <div className="row" style={{ justifyContent: "center", marginTop: 10 }}>
        <button disabled title="Coming soon">Reschedule</button>
        <button disabled title="Coming soon">Cancel booking</button>
      </div>
      <p className="muted" style={{ marginTop: 12 }}>Reminders 24 hours and 2 hours before.</p>
    </div></div>
  );
}
