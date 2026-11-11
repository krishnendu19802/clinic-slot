import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useDoctor, useGrid, usePolicy } from "../api/queries";
import type { Booking, GridSlot } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Avatar, ErrorBox, Loading, NotFound, Verified } from "../components/bits";
import { addDays, dateLong, dayParts, rupees, time, todayKey } from "../lib/format";

export default function DoctorProfile() {
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: doc, error: docError } = useDoctor(id);
  const { data: policy } = usePolicy();
  const clinic = doc?.clinics.find((c) => String(c.id) === params.get("clinic")) ?? doc?.clinics[0];
  const [weekStart, setWeekStart] = useState(todayKey());
  const { data: days, isFetching } = useGrid(id, clinic?.id, weekStart);
  const [date, setDate] = useState(params.get("date") ?? "");
  const [slot, setSlot] = useState<GridSlot | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const day = days?.find((d) => d.date === date);
  const openCount = (d: { windows: { slots: GridSlot[] }[] }) => d.windows.flatMap((w) => w.slots).filter((s) => s.available).length;

  // Pick the first day with space when none (or an out-of-range one) is chosen.
  useEffect(() => {
    if (days && !days.some((d) => d.date === date)) setDate((days.find((d) => openCount(d) > 0) ?? days[0])!.date);
  }, [days, date]);

  // Preselect a slot passed from the results page, once the grid shows it.
  const wanted = Number(params.get("slot") ?? 0);
  useEffect(() => {
    const hit = day?.windows.flatMap((w) => w.slots).find((s) => s.id === wanted && s.available);
    if (hit) setSlot(hit);
  }, [day, wanted]);

  const book = async () => {
    if (!slot) return;
    if (user?.role !== "patient") { navigate("/login", { state: { next: `/doctors/${id}?${params}`, role: "patient" } }); return; }
    setBusy(true); setError(null);
    try {
      const b = await api<Booking>("/bookings", { method: "POST", body: { slot_id: slot.id } });
      qc.invalidateQueries({ queryKey: ["holds"] });
      navigate(`/book/${b.id}/${b.patient ? "payment" : "details"}`);
    } catch (e) {
      setError(e);
      if (e instanceof ApiError && ["SLOT_TAKEN", "TOO_LATE"].includes(e.code)) { setSlot(null); qc.invalidateQueries({ queryKey: ["grid"] }); }
    } finally { setBusy(false); }
  };

  const overlapNote = useMemo(() => {
    if (!(error instanceof ApiError) || error.code !== "BOOKING_OVERLAP") return null;
    const c = error.details.conflicting_booking;
    return (
      <div className="alert" role="alert">
        This time overlaps your {c.status === "pending_payment" ? "unfinished booking" : "booking"} with {c.doctor_name} ({c.ref}).{" "}
        <Link to={c.status === "pending_payment" ? `/book/${c.id}/details` : `/book/${c.id}/confirmed`}>
          {c.status === "pending_payment" ? "Continue that booking" : "View it"}
        </Link>
      </div>
    );
  }, [error]);

  if (docError) return <NotFound>Doctor not found</NotFound>;
  if (!doc || !clinic) return <Loading />;
  const d = doc.doctor;

  return (
    <div className="wrap">
      <div className="row top">
        <div className="card grow" style={{ minWidth: 300 }}>
          <div className="row" style={{ gap: 18 }}>
            <Avatar name={d.name} />
            <div>
              <h1>{d.name} <Verified /></h1>
              <p className="muted">{d.specialities.map((s) => s.name).join(", ")} · {d.degrees.join(", ")}</p>
              <p className="muted">Reg. {d.registration_no}{d.council ? `, ${d.council}` : ""}</p>
            </div>
          </div>
          <div className="row" style={{ marginTop: 16, gap: 28 }}>
            <div><b>{d.experience_years} yrs</b><p className="muted">Experience</p></div>
            <div><b>{rupees(d.fee_paise)}</b><p className="muted">Consultation fee</p></div>
            <div><b>{d.languages.join(", ")}</b><p className="muted">Languages</p></div>
          </div>
          {d.remarks && <><h3 style={{ marginTop: 18 }}>About</h3><p className="muted">{d.remarks}</p></>}
        </div>
        <div className="card" style={{ flex: "0 0 320px" }}>
          <h3>Clinic</h3>
          {doc.clinics.length > 1 && (
            <label style={{ margin: "8px 0" }}>Choose clinic
              <select value={clinic.id} onChange={(e) => { setParams({ clinic: e.target.value }); setSlot(null); }}>
                {doc.clinics.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
          )}
          <p style={{ margin: "6px 0" }}>{clinic.name}, {clinic.address}, {clinic.city}</p>
          <p className="muted" style={{ marginBottom: 10 }}>{clinic.schedule_summary}</p>
          <a className="map" href={`https://www.google.com/maps/search/?api=1&query=${clinic.lat},${clinic.lng}`} target="_blank" rel="noreferrer">
            Map placeholder · Open in Google Maps
          </a>
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Select date and time</h2>
          <div className="row" style={{ gap: 8 }}>
            <button disabled={weekStart <= todayKey()} onClick={() => setWeekStart(addDays(weekStart, -7))}>← Earlier</button>
            <button onClick={() => setWeekStart(addDays(weekStart, 7))}>Later →</button>
          </div>
        </div>
        <div className="days" style={{ margin: "14px 0" }} role="tablist" aria-label="Dates">
          {days?.map((x) => {
            const n = openCount(x), p = dayParts(x.date);
            const off = x.windows.length === 0;
            return (
              <button key={x.date} role="tab" aria-selected={x.date === date} disabled={off} className={`day${x.date === date ? " on" : ""}${off ? " off" : ""}`}
                onClick={() => { setDate(x.date); setSlot(null); }}>
                <small>{p.weekday}</small><b style={{ fontSize: 18 }}>{p.dom}</b><small>{off ? "Off" : n === 0 ? "Full" : `${n} slot${n === 1 ? "" : "s"}`}</small>
              </button>
            );
          })}
        </div>
        {isFetching && !days && <p className="muted">Loading slots…</p>}
        {day?.windows.map((w) => (
          <div key={w.start_time} style={{ marginBottom: 14 }}>
            <p className="muted" style={{ marginBottom: 8 }}>{w.start_time} to {w.end_time} · {w.slot_minutes} min per slot</p>
            <div className="row" style={{ gap: 8 }}>
              {w.slots.map((s) => {
                const blocked = s.available && s.overlaps_mine;
                return (
                  <button key={s.id} className={`slot${slot?.id === s.id ? " on" : ""}${!s.available ? " gone" : ""}${s.held_by_me ? " mine" : ""}`}
                    disabled={!s.available || blocked} aria-pressed={slot?.id === s.id}
                    title={blocked ? "Overlaps another booking of yours" : s.held_by_me ? "You are holding this slot" : undefined}
                    onClick={() => setSlot(s)}>{time(s.start)}</button>
                );
              })}
            </div>
          </div>
        ))}
        <p className="muted">Struck-through slots are booked or being held by another patient.</p>
        {day && day.windows.length === 0 && <p className="muted">The doctor does not see patients on this day.</p>}
      </div>

      {overlapNote ?? <ErrorBox error={error} />}
      {slot && (
        <div className="sbar" role="region" aria-label="Your selection">
          <div>
            <b>{dateLong(slot.start)} · {time(slot.start)}</b>
            <p style={{ color: "#c7cedd", fontSize: 13 }}>
              {rupees(d.fee_paise)} · free cancellation up to {policy?.free_cancel_hours ?? 4} hrs
            </p>
          </div>
          <button className="primary" onClick={book} disabled={busy}>{busy ? "Holding…" : "Book slot"}</button>
        </div>
      )}
    </div>
  );
}
