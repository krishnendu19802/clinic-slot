import { useState } from "react";
import { Link } from "react-router-dom";
import { useBookings } from "../api/queries";
import { useAuth } from "../auth/AuthContext";
import { Avatar, ErrorBox, Loading, NeedLogin } from "../components/bits";
import { dateTime } from "../lib/format";

const TABS = [["upcoming", "Upcoming"], ["past", "Past"], ["cancelled", "Cancelled"]] as const;

export default function Bookings() {
  const { user, loading } = useAuth();
  const [tab, setTab] = useState<string>("upcoming");
  const { data, error, isLoading } = useBookings(tab);
  if (loading) return <Loading />;
  if (!user) return <NeedLogin role="patient" next="/bookings" />;
  return (
    <div className="wrap">
      <h1>My bookings</h1>
      <div className="tabs" role="tablist">
        {TABS.map(([k, label]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{label}</button>)}
      </div>
      <ErrorBox error={error} />
      {isLoading && <p className="muted">Loading…</p>}
      {data?.items.length === 0 && <div className="card center"><p className="muted">Nothing here yet.</p><Link to="/doctors">Find a doctor</Link></div>}
      {data?.items.map((b) => (
        <div className="card row" key={b.id} style={{ gap: 16 }}>
          <Avatar name={b.doctor.name} small />
          <div className="grow">
            <b>{b.doctor.name} · token {b.token}</b>
            <p className="muted">{dateTime(b.slot.start)} · {b.clinic.name}, {b.clinic.area}</p>
            <p className="muted">{b.ref}</p>
          </div>
          <span className={`pill${b.status === "cancelled" ? " red" : b.status === "confirmed" ? "" : " grey"}`}>{b.status.replace("_", " ")}</span>
          {b.refund && <span className="pill amber">Refund {b.refund.status}</span>}
          <Link className="btn" to={`/book/${b.id}/confirmed`}>View</Link>
        </div>
      ))}
    </div>
  );
}
