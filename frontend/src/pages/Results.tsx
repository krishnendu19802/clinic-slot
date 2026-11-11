import { Link, useSearchParams } from "react-router-dom";
import { useSearch, useSpecialities } from "../api/queries";
import type { SearchItem } from "../api/types";
import { Avatar, ErrorBox, Verified } from "../components/bits";
import { dateTime, dayLabel, rupees, time } from "../lib/format";

function Availability({ item, doctorLink }: { item: SearchItem; doctorLink: (slot?: number) => string }) {
  const a = item.availability;
  const label = dayLabel(a.date);
  return (
    <>
      {a.day_state === "open" ? (
        <p className="muted" style={{ margin: "12px 0 6px", fontWeight: 700, color: "var(--green)" }}>{label} · {a.slots_left} slot{a.slots_left === 1 ? "" : "s"} left</p>
      ) : (
        <p className="muted" style={{ margin: "12px 0 6px", fontWeight: 700, color: "var(--amber)" }}>
          {a.day_state === "full" ? `Fully booked ${label.toLowerCase()}` : `Doctor off ${label.toLowerCase()}`}
          {a.next_available_start && <span className="muted"> · Next: {dateTime(a.next_available_start)}</span>}
        </p>
      )}
      <div className="row" style={{ gap: 8 }}>
        {a.preview_slots.map((s) => <Link key={s.slot_id} className="btn slot" to={doctorLink(s.slot_id)}>{time(s.start)}</Link>)}
      </div>
    </>
  );
}

const SORTS = [["earliest", "Earliest availability"], ["fee", "Fee: low to high"], ["experience", "Most experienced"], ["distance", "Nearest"]];

export default function Results() {
  const [params, setParams] = useSearchParams();
  const p = Object.fromEntries(params) as Record<string, string>;
  const { data, isLoading, error } = useSearch(p);
  const { data: specialities = [] } = useSpecialities();
  const set = (k: string, v: string) => setParams((cur) => {
    const next = new URLSearchParams(cur);
    if (v) next.set(k, v); else next.delete(k);
    next.delete("page");
    return next;
  }, { replace: true });
  const page = Number(p.page ?? 1);
  const specialityName = specialities.find((s) => s.slug === p.speciality)?.name ?? "Doctors";
  const detailLink = (item: SearchItem) => (slot?: number) =>
    `/doctors/${item.doctor.id}?${new URLSearchParams({ clinic: String(item.clinic.id), date: item.availability.date, ...(slot ? { slot: String(slot) } : {}) })}`;

  return (
    <div className="wrap">
      <div className="row">
        <div className="grow">
          <h1>{specialityName}{p.city ? ` in ${p.city}` : ""}</h1>
          <p className="muted">{data ? `${data.total} verified doctor${data.total === 1 ? "" : "s"}` : "Searching…"}</p>
        </div>
        <label style={{ flex: "0 0 220px" }}>Sort by
          <select value={p.sort ?? "earliest"} onChange={(e) => set("sort", e.target.value)}>
            {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      <div className="row top">
        <div className="grow" style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 300 }}>
          <ErrorBox error={error} />
          {isLoading && <p className="muted">Loading…</p>}
          {data?.items.length === 0 && <div className="card center"><h3>No doctors with open slots match this search</h3><p className="muted">Try another date or remove a filter.</p></div>}
          {data?.items.map((item) => (
            <div className="card row top" key={`${item.doctor.id}-${item.clinic.id}`} style={{ gap: 18 }}>
              <Avatar name={item.doctor.name} />
              <div className="grow" style={{ minWidth: 240 }}>
                <h3>{item.doctor.name} <Verified /></h3>
                <p className="muted">{item.doctor.degrees.join(", ")} · {item.doctor.experience_years} years</p>
                <p className="muted">{item.clinic.name}, {item.clinic.area}{item.clinic.distance_km !== null ? ` · ${item.clinic.distance_km} km` : ""}</p>
                <Availability item={item} doctorLink={detailLink(item)} />
              </div>
              <div style={{ textAlign: "right" }}>
                <b style={{ fontSize: 24 }}>{rupees(item.doctor.fee_paise)}</b><p className="muted" style={{ marginBottom: 10 }}>per visit</p>
                <Link className="btn primary" to={detailLink(item)()}>View and book</Link>
              </div>
            </div>
          ))}
          {data && data.total > data.page_size && (
            <div className="row" style={{ justifyContent: "center" }}>
              <button disabled={page <= 1} onClick={() => set("page", String(page - 1))}>Previous</button>
              <span className="muted">Page {page} of {Math.ceil(data.total / data.page_size)}</span>
              <button disabled={page * data.page_size >= data.total} onClick={() => set("page", String(page + 1))}>Next</button>
            </div>
          )}
        </div>
        <aside className="card" style={{ flex: "0 0 260px", display: "flex", flexDirection: "column", gap: 14 }}>
          <h2>Refine</h2>
          <label>Speciality
            <select value={p.speciality ?? ""} onChange={(e) => set("speciality", e.target.value)}>
              <option value="">Any</option>{specialities.map((s) => <option key={s.slug} value={s.slug}>{s.name}</option>)}
            </select>
          </label>
          <label>Date<input type="date" value={p.date ?? ""} onChange={(e) => set("date", e.target.value)} /></label>
          <label>Fee
            <select value={p.fee_max ?? ""} onChange={(e) => set("fee_max", e.target.value)}>
              <option value="">Any</option><option value="50000">Under ₹500</option><option value="100000">Under ₹1,000</option>
            </select>
          </label>
          <label>Experience
            <select value={p.experience_min ?? ""} onChange={(e) => set("experience_min", e.target.value)}>
              <option value="">Any</option><option value="5">5+ years</option><option value="10">10+ years</option>
            </select>
          </label>
          <label>Language
            <select value={p.language ?? ""} onChange={(e) => set("language", e.target.value)}>
              <option value="">Any</option><option>English</option><option>Bengali</option><option>Hindi</option>
            </select>
          </label>
          <label>Doctor
            <select value={p.gender ?? ""} onChange={(e) => set("gender", e.target.value)}>
              <option value="">Any</option><option value="female">Female</option><option value="male">Male</option>
            </select>
          </label>
        </aside>
      </div>
    </div>
  );
}
