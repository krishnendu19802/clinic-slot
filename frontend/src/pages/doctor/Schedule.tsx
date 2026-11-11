import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../../api/client";
import { useClinics, useDoctorSlots, useSchedule } from "../../api/queries";
import type { Clinic, Conflict, GenerationResult, ScheduleWindow } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { ErrorBox, Loading, RequireRole } from "../../components/bits";
import { dateTime, todayKey, time, windowProblem, windowSlots } from "../../lib/format";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const LENGTHS = [10, 12, 15, 20, 30, 60];
const EMPTY_CLINIC = { name: "", address: "", area: "", city: "Durgapur", pincode: "", phone: "", lat: "23.5204", lng: "87.3119" };

function useRun() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError(null);
    try { await fn(); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  return { busy, error, run, setError };
}

function ClinicForm({ initial, onSaved, onCancel }: { initial?: Clinic; onSaved: (c: Clinic) => void; onCancel?: () => void }) {
  const qc = useQueryClient();
  const [f, setF] = useState(initial ? { ...EMPTY_CLINIC, ...initial } : EMPTY_CLINIC);
  const { busy, error, run } = useRun();
  const set = (k: keyof typeof EMPTY_CLINIC, v: string) => setF({ ...f, [k]: v });
  const locate = () => navigator.geolocation?.getCurrentPosition((p) => setF((c) => ({ ...c, lat: p.coords.latitude.toFixed(6), lng: p.coords.longitude.toFixed(6) })));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    run(async () => {
      const body = { name: f.name, address: f.address, area: f.area, city: f.city, pincode: f.pincode, phone: f.phone, lat: f.lat, lng: f.lng };
      const c = initial
        ? await api<Clinic>(`/doctor/clinics/${initial.id}`, { method: "PATCH", body })
        : await api<Clinic>("/doctor/clinics", { method: "POST", body });
      await qc.invalidateQueries({ queryKey: ["clinics"] });
      onSaved(c);
    });
  };
  const fields = error instanceof ApiError ? error.fields : {};
  return (
    <form className="card" onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <h2 style={{ margin: 0 }}>{initial ? "Edit clinic" : "Add your clinic"}</h2>
      <div className="fgrid">
        <label>Clinic name<input required value={f.name} onChange={(e) => set("name", e.target.value)} /></label>
        <label>Address<input required value={f.address} onChange={(e) => set("address", e.target.value)} /></label>
        <label>Area<input required value={f.area} onChange={(e) => set("area", e.target.value)} /></label>
        <label>City<input required value={f.city} onChange={(e) => set("city", e.target.value)} /></label>
        <label>Pincode<input required value={f.pincode} onChange={(e) => set("pincode", e.target.value)} inputMode="numeric" /></label>
        <label>Contact number<input value={f.phone} onChange={(e) => set("phone", e.target.value)} inputMode="tel" /></label>
        <label>Map pin: latitude<input required value={f.lat} onChange={(e) => set("lat", e.target.value)} inputMode="decimal" /></label>
        <label>Map pin: longitude<input required value={f.lng} onChange={(e) => set("lng", e.target.value)} inputMode="decimal" /></label>
      </div>
      <button type="button" className="link" onClick={locate} style={{ alignSelf: "flex-start" }}>Use my current location for the pin</button>
      {Object.keys(fields).length > 0 && <div className="alert" role="alert">{Object.entries(fields).map(([k, v]) => `${k}: ${[v].flat().join(", ")}`).join(" · ")}</div>}
      {Object.keys(fields).length === 0 && <ErrorBox error={error} />}
      <div className="row">
        <button className="primary" disabled={busy}>{initial ? "Save clinic" : "Add clinic"}</button>
        {onCancel && <button type="button" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}

function Conflicts({ items }: { items: Conflict[] }) {
  if (!items.length) return null;
  return (
    <div className="alert" role="alert">
      <b>{items.length} booking{items.length === 1 ? "" : "s"} need attention.</b> They were not cancelled. Contact the patients to move or cancel them:
      <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
        {items.map((c) => <li key={c.booking_id}>{c.ref} · {c.patient_name || "patient"} · {dateTime(c.start)} ({c.reason === "day_blocked" ? "day blocked" : "window removed"})</li>)}
      </ul>
    </div>
  );
}

function WeeklyHours({ clinic, approved }: { clinic: Clinic; approved: boolean }) {
  const qc = useQueryClient();
  const { data } = useSchedule(clinic.id);
  const [rows, setRows] = useState<ScheduleWindow[] | null>(null);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const { busy, error, run } = useRun();
  useEffect(() => { setRows(null); setResult(null); }, [clinic.id]);
  useEffect(() => { if (data && !rows) setRows(data.windows.map(({ weekday, start_time, end_time, slot_minutes }) => ({ weekday, start_time, end_time, slot_minutes }))); }, [data, rows]);
  if (!rows) return <p className="muted">Loading schedule…</p>;

  const patch = (i: number, p: Partial<ScheduleWindow>) => { setRows(rows.map((r, j) => (j === i ? { ...r, ...p } : r))); setResult(null); };
  const problems = rows.map((r) => windowProblem(r.start_time, r.end_time, r.slot_minutes));
  const save = () => run(async () => {
    const r = await api<GenerationResult>(`/doctor/clinics/${clinic.id}/schedule`, { method: "PUT", body: { windows: rows } });
    setResult(r);
    await qc.invalidateQueries({ queryKey: ["schedule", clinic.id] });
  });

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <h2>Weekly hours</h2>
      {rows.length === 0 && <p className="muted">No hours yet. Add a window for each day you see patients.</p>}
      {rows.map((r, i) => (
        <div key={i} style={{ padding: "12px 0", borderBottom: "1px solid #eef0f6" }}>
          <div className="row" style={{ alignItems: "flex-end" }}>
            <label style={{ flex: "0 0 90px", minWidth: 0 }}>Day
              <select value={r.weekday} onChange={(e) => patch(i, { weekday: Number(e.target.value) })}>{DAYS.map((d, k) => <option key={d} value={k + 1}>{d}</option>)}</select>
            </label>
            <label style={{ minWidth: 120 }}>From<input type="time" value={r.start_time} onChange={(e) => patch(i, { start_time: e.target.value })} /></label>
            <label style={{ minWidth: 120 }}>To<input type="time" value={r.end_time} onChange={(e) => patch(i, { end_time: e.target.value })} /></label>
            <label style={{ flex: "0 0 130px", minWidth: 0 }}>Slot length
              <select value={r.slot_minutes} onChange={(e) => patch(i, { slot_minutes: Number(e.target.value) })}>{LENGTHS.map((m) => <option key={m} value={m}>{m} min</option>)}</select>
            </label>
            <button type="button" onClick={() => { setRows(rows.filter((_, j) => j !== i)); setResult(null); }} aria-label={`Remove ${DAYS[r.weekday - 1]} window`}>✕</button>
          </div>
          {problems[i]
            ? <p className="muted" style={{ color: "var(--red)", marginTop: 6 }}>{problems[i]}</p>
            : <p className="muted" style={{ marginTop: 6 }}>{windowSlots(r.start_time, r.end_time, r.slot_minutes).length} slots of {r.slot_minutes} min</p>}
        </div>
      ))}
      <div className="row" style={{ marginTop: 12 }}>
        <button type="button" onClick={() => setRows([...rows, { weekday: 1, start_time: "16:00", end_time: "17:00", slot_minutes: 12 }])}>+ Add window</button>
        <button className="primary" onClick={save} disabled={busy || problems.some(Boolean)}>Save schedule</button>
      </div>
      {rows[0] && !problems[0] && (
        <p className="muted" style={{ marginTop: 10 }}>
          Preview: {DAYS[rows[0].weekday - 1]} {rows[0].start_time} to {rows[0].end_time}: {windowSlots(rows[0].start_time, rows[0].end_time, rows[0].slot_minutes).join(" · ")}
        </p>
      )}
      <ErrorBox error={error} />
      {result && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          <div className="alert ok" role="status">
            {approved ? `Saved. ${result.slots_generated} new slot${result.slots_generated === 1 ? "" : "s"} are now bookable.` : "Saved. Slots become bookable once an admin approves your profile."}
          </div>
          <Conflicts items={result.conflicts} />
        </div>
      )}
    </div>
  );
}

function BlockPanel({ clinic }: { clinic: Clinic }) {
  const qc = useQueryClient();
  const { data: schedule } = useSchedule(clinic.id);
  const [date, setDate] = useState(todayKey());
  const { data: slots } = useDoctorSlots(clinic.id, date);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const { busy, error, run } = useRun();
  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: ["schedule", clinic.id] }), qc.invalidateQueries({ queryKey: ["doctor-slots"] })]);

  const blockDay = () => run(async () => {
    const r = await api<GenerationResult>(`/doctor/clinics/${clinic.id}/exceptions`, { method: "POST", body: { date, type: "blocked" } });
    setConflicts(r.conflicts); await refresh();
  });
  const unblockDay = (id: number) => run(async () => { await api(`/doctor/clinics/${clinic.id}/exceptions/${id}`, { method: "DELETE" }); await refresh(); });
  const toggleSlot = (id: number, blocked: boolean) => run(async () => {
    await api(`/doctor/slots/${id}/block`, { method: blocked ? "DELETE" : "POST" });
    await refresh();
  });

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <h2 style={{ margin: 0 }}>Block a day or slot</h2>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <label style={{ maxWidth: 220 }}>Date<input type="date" min={todayKey()} value={date} onChange={(e) => setDate(e.target.value)} /></label>
        <button onClick={blockDay} disabled={busy || !date}>Block day</button>
      </div>
      {slots && slots.length > 0 && (
        <div>
          <p className="muted" style={{ marginBottom: 8 }}>Tap a slot to block or unblock it.</p>
          <div className="row" style={{ gap: 8 }}>
            {slots.map((s) => (
              <button key={s.id} className={`slot${s.status === "blocked" ? " gone" : ""}${s.status === "booked" || s.status === "held" ? " on" : ""}`}
                disabled={busy || s.status === "booked" || s.status === "held"} onClick={() => toggleSlot(s.id, s.status === "blocked")}
                title={s.status === "booked" ? "Booked" : s.status === "held" ? "A patient is booking this" : s.status === "blocked" ? "Blocked: tap to unblock" : "Tap to block"}>
                {time(s.start)}{s.status === "booked" ? " · booked" : ""}
              </button>
            ))}
          </div>
        </div>
      )}
      {slots && slots.length === 0 && <p className="muted">No slots on this date (day off, or none generated yet).</p>}
      <p className="muted">Existing bookings are flagged for you, never cancelled automatically.</p>
      <Conflicts items={conflicts} />
      <ErrorBox error={error} />
      {schedule && schedule.exceptions.length > 0 && (
        <div>
          <h3 style={{ marginBottom: 6 }}>Days off and extra hours</h3>
          {schedule.exceptions.map((x) => (
            <div key={x.id} className="row" style={{ justifyContent: "space-between", padding: "6px 0" }}>
              <span>{x.date} · {x.type === "blocked" ? (x.start_time ? `blocked ${x.start_time} to ${x.end_time}` : "day off") : `extra hours ${x.start_time} to ${x.end_time}`}</span>
              <button className="link" onClick={() => unblockDay(x.id)} aria-label={`Remove ${x.date}`}>Remove</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Page() {
  const { user } = useAuth();
  const { data: clinics, isLoading } = useClinics();
  const [selected, setSelected] = useState<number | null>(null);
  const [mode, setMode] = useState<"view" | "add" | "edit">("view");
  if (isLoading || !clinics) return <Loading />;
  const clinic = clinics.find((c) => c.id === selected) ?? clinics[0];
  const approved = user?.doctor?.verification_status === "approved";

  return (
    <div className="wrap">
      <div><h1>Clinic and schedule</h1><p className="muted">Your hours become bookable slots automatically.</p></div>
      {!approved && <div className="alert info" role="status">Your profile is not approved yet, so no slots are visible to patients. You can set everything up now.</div>}
      {!clinic || mode === "add" ? (
        <ClinicForm onSaved={(c) => { setSelected(c.id); setMode("view"); }} onCancel={clinic ? () => setMode("view") : undefined} />
      ) : (
        <>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div className="row">
              {clinics.length > 1 ? (
                <select aria-label="Clinic" value={clinic.id} onChange={(e) => setSelected(Number(e.target.value))} style={{ width: "auto" }}>
                  {clinics.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              ) : <h2 style={{ margin: 0 }}>{clinic.name}</h2>}
              <span className="muted">{clinic.address}, {clinic.area}, {clinic.city}</span>
            </div>
            <div className="row"><button onClick={() => setMode("edit")}>Edit clinic</button><button onClick={() => setMode("add")}>+ Add clinic</button></div>
          </div>
          {mode === "edit" ? <ClinicForm initial={clinic} onSaved={() => setMode("view")} onCancel={() => setMode("view")} /> : null}
          <div className="row top">
            <div style={{ flex: "2 1 560px", minWidth: 0 }}><WeeklyHours clinic={clinic} approved={approved} /></div>
            <div style={{ flex: "1 1 300px", minWidth: 0 }}><BlockPanel clinic={clinic} /></div>
          </div>
        </>
      )}
    </div>
  );
}

export default function Schedule() { return <RequireRole role="doctor"><Page /></RequireRole>; }
