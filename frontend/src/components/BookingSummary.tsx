import type { Booking } from "../api/types";
import { dateLong, mmss, rupees, time } from "../lib/format";
import { Avatar } from "./bits";

export default function BookingSummary({ booking, left }: { booking: Booking; left: number | null }) {
  return (
    <div className="card">
      <h2>Booking summary</h2>
      <div className="row" style={{ flexWrap: "nowrap" }}>
        <Avatar name={booking.doctor.name} small />
        <div><b>{booking.doctor.name}</b><p className="muted">{booking.clinic.name}, {booking.clinic.area}</p></div>
      </div>
      <hr style={{ border: 0, borderTop: "1px solid #eef0f6", margin: "16px 0" }} />
      <p>{dateLong(booking.slot.start)}, {time(booking.slot.start)} to {time(booking.slot.end)}</p>
      <p className="muted">Slot {booking.slot.seq} of {booking.slot.window_total} · Token {booking.token}</p>
      <hr style={{ border: 0, borderTop: "1px solid #eef0f6", margin: "16px 0" }} />
      <div className="row" style={{ justifyContent: "space-between" }}><span>Consultation fee</span><b style={{ fontSize: 20 }}>{rupees(booking.fee_paise)}</b></div>
      {left !== null && booking.status === "pending_payment" && (
        <p className="hold" style={{ marginTop: 14 }} aria-live="polite">Slot held for {mmss(left)}</p>
      )}
    </div>
  );
}
