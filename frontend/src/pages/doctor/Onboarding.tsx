import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import { useCouncils, useDoctorDocuments, useDoctorProfile, useSpecialities } from "../../api/queries";
import type { DocType, DoctorProfileData, Verification } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { ErrorBox, Loading, RequireRole } from "../../components/bits";

const EDITABLE: Verification[] = ["draft", "info_requested", "rejected"];
const LANGUAGES = ["English", "Bengali", "Hindi"];
const DOCS: { type: DocType; label: string }[] = [
  { type: "registration", label: "Registration certificate" }, { type: "degree", label: "Degree certificate" }, { type: "id", label: "Government ID" },
];
const STATUS_TEXT: Record<Verification, { pill: string; cls: string; text: string }> = {
  draft: { pill: "Not submitted", cls: "amber", text: "Your profile stays hidden from search until an admin approves it. You will get an SMS when the review is done." },
  submitted: { pill: "Under review", cls: "amber", text: "We are reviewing your registration and documents. You cannot edit while it is under review." },
  info_requested: { pill: "More info needed", cls: "amber", text: "The reviewer needs more information. Update your profile or documents and submit again." },
  approved: { pill: "Verified", cls: "", text: "You are live. Patients can find you and book the slots you set in your schedule." },
  rejected: { pill: "Rejected", cls: "red", text: "Your submission was rejected. Fix the issues below and submit again." },
  suspended: { pill: "Suspended", cls: "red", text: "Your profile is hidden from search. Contact support." },
};
const FIELD_LABELS: Record<string, string> = {
  full_name: "Full name", gender: "Gender", registration_no: "Registration number", council: "Issuing council", degrees: "Degrees",
  experience_years: "Experience", fee_paise: "Consultation fee", languages: "Languages", specialities: "Speciality",
  document_registration: "Registration certificate", document_degree: "Degree certificate", document_id: "Government ID",
};

type Form = Omit<DoctorProfileData, "verification_status" | "status_reason" | "registry_check" | "fee_paise"> & { fee: string };
const toForm = (p: DoctorProfileData): Form => ({ ...p, fee: p.fee_paise ? String(p.fee_paise / 100) : "" });
const toBody = (f: Form) => ({
  full_name: f.full_name, gender: f.gender, registration_no: f.registration_no, council_id: f.council_id,
  degrees: f.degrees, specialities: f.specialities, experience_years: f.experience_years,
  fee_paise: f.fee ? Math.round(Number(f.fee) * 100) : null, languages: f.languages, remarks: f.remarks,
});

function Page() {
  const qc = useQueryClient();
  const { user, refreshUser } = useAuth();
  const { data: profile } = useDoctorProfile();
  const { data: docs = [] } = useDoctorDocuments();
  const { data: councils = [] } = useCouncils();
  const { data: specialities = [] } = useSpecialities();
  const [form, setForm] = useState<Form | null>(null);
  const [degrees, setDegrees] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => { if (profile && !form) { setForm(toForm(profile)); setDegrees(profile.degrees.join(", ")); } }, [profile, form]);
  if (!profile || !form) return <Loading />;

  const locked = !EDITABLE.includes(profile.verification_status);
  const status = STATUS_TEXT[profile.verification_status];
  const set = <K extends keyof Form>(k: K, v: Form[K]) => { setForm({ ...form, [k]: v }); setSaved(false); };
  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const body = () => toBody({ ...form, degrees: degrees.split(",").map((d) => d.trim()).filter(Boolean) });

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError(null); setSaved(false);
    try { await fn(); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const save = () => run(async () => {
    await api("/doctor/profile", { method: "PATCH", body: body() });
    await qc.invalidateQueries({ queryKey: ["doctor-profile"] });
    setSaved(true);
  });
  const submit = () => run(async () => {
    await api("/doctor/profile", { method: "PATCH", body: body() });
    await api("/doctor/profile/submit", { method: "POST" });
    await qc.invalidateQueries({ queryKey: ["doctor-profile"] });
    await refreshUser();
    setForm(null);
  });

  const upload = (type: DocType) => (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { setError(new ApiError(400, "VALIDATION_ERROR", "File is larger than 5 MB")); return; }
    run(async () => {
      const fd = new FormData();
      fd.append("type", type); fd.append("file", file);
      await api("/doctor/documents", { method: "POST", form: fd });
      await qc.invalidateQueries({ queryKey: ["doctor-docs"] });
    });
  };
  const remove = (id: number) => run(async () => {
    await api(`/doctor/documents/${id}`, { method: "DELETE" });
    await qc.invalidateQueries({ queryKey: ["doctor-docs"] });
  });

  const missing = error instanceof ApiError && error.code === "VALIDATION_ERROR" && error.fields
    ? Object.keys(error.fields).map((k) => FIELD_LABELS[k] ?? k) : [];

  return (
    <div className="wrap">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div><h1>{locked ? "Your profile" : "Complete your profile"}</h1><p className="muted">Patients see this after an admin verifies your registration.</p></div>
        <span className={`pill ${status.cls}`}>{status.pill}</span>
      </div>
      <div className="steps" aria-hidden="true">
        <span className="steps"><i>1</i> Profile</span><hr /><span className="steps"><i className={docs.length ? "" : "off"}>2</i> Documents</span><hr />
        <span className="steps"><i className={locked ? "" : "off"}>3</i> Submit</span>
      </div>
      {profile.status_reason && <div className="alert info"><b>Reviewer note:</b> {profile.status_reason}</div>}

      <div className="row top">
        <div className="grow" style={{ display: "flex", flexDirection: "column", gap: 20, minWidth: 320 }}>
          <fieldset className="card" disabled={locked || busy} style={{ border: "1px solid var(--line)", margin: 0 }}>
            <h2>Professional details</h2>
            <div className="fgrid">
              <label>Full name<input value={form.full_name} onChange={(e) => set("full_name", e.target.value)} /></label>
              <label>Registration number<input value={form.registration_no} onChange={(e) => set("registration_no", e.target.value)} placeholder="e.g. WBMC-0000" /></label>
              <label>Issuing council
                <select value={form.council_id ?? ""} onChange={(e) => set("council_id", e.target.value ? Number(e.target.value) : null)}>
                  <option value="">Select</option>{councils.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </label>
              <label>Degrees<input value={degrees} onChange={(e) => { setDegrees(e.target.value); setSaved(false); }} placeholder="MBBS, MD" /></label>
              <label>Gender
                <select value={form.gender} onChange={(e) => set("gender", e.target.value as Form["gender"])}>
                  <option value="">Select</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
                </select>
              </label>
              <label>Experience (years)<input type="number" min={0} value={form.experience_years ?? ""} onChange={(e) => set("experience_years", e.target.value === "" ? null : Number(e.target.value))} /></label>
              <label>Consultation fee (₹)<input type="number" min={0} value={form.fee} onChange={(e) => set("fee", e.target.value)} /></label>
            </div>
            <p style={{ margin: "16px 0 6px", fontWeight: 700, fontSize: 13, color: "#475467" }}>Speciality</p>
            <div className="row" style={{ gap: 8 }}>
              {specialities.map((s) => (
                <label key={s.id} style={{ flexDirection: "row", alignItems: "center", flex: "none", minWidth: 0, fontWeight: 600, gap: 6 }}>
                  <input type="checkbox" style={{ width: "auto", minHeight: 0 }} checked={form.specialities.includes(s.id)} onChange={() => set("specialities", toggle(form.specialities, s.id))} />{s.name}
                </label>
              ))}
            </div>
            <p style={{ margin: "16px 0 6px", fontWeight: 700, fontSize: 13, color: "#475467" }}>Languages</p>
            <div className="row" style={{ gap: 14 }}>
              {LANGUAGES.map((l) => (
                <label key={l} style={{ flexDirection: "row", alignItems: "center", flex: "none", minWidth: 0, fontWeight: 600, gap: 6 }}>
                  <input type="checkbox" style={{ width: "auto", minHeight: 0 }} checked={form.languages.includes(l)} onChange={() => set("languages", toggle(form.languages, l))} />{l}
                </label>
              ))}
            </div>
            <label style={{ marginTop: 16 }}>Remarks / bio<input value={form.remarks} onChange={(e) => set("remarks", e.target.value)} placeholder="A short note patients will see" /></label>
          </fieldset>

          <fieldset className="card" disabled={locked || busy} style={{ border: "1px solid var(--line)", margin: 0 }}>
            <h2>Documents</h2>
            <div className="fgrid">
              {DOCS.map(({ type, label }) => {
                const doc = docs.find((d) => d.type === type);
                return (
                  <div className="upload" key={type}>
                    {label}<br />
                    {doc ? (
                      <><span className="muted">{doc.name} · {Math.max(1, Math.round(doc.size_bytes / 1024))} KB</span><br />
                        <button type="button" className="link" onClick={() => remove(doc.id)} aria-label={`Remove ${label}`}>Remove</button></>
                    ) : (
                      <><span className="muted">PDF, JPG or PNG, max 5 MB</span><br />
                        <input type="file" accept="application/pdf,image/jpeg,image/png" onChange={upload(type)} aria-label={`Upload ${label}`} style={{ marginTop: 8, minHeight: 0, border: 0 }} /></>
                    )}
                  </div>
                );
              })}
            </div>
          </fieldset>

          {missing.length > 0 && <div className="alert" role="alert">Still needed: {missing.join(", ")}</div>}
          {missing.length === 0 && <ErrorBox error={error} />}
          {saved && <div className="alert ok" role="status">Draft saved.</div>}
          {!locked && (
            <div className="row">
              <button className="primary" onClick={submit} disabled={busy}>Submit for verification</button>
              <button onClick={save} disabled={busy}>Save draft</button>
            </div>
          )}
        </div>

        <div className="card" style={{ flex: "0 0 280px" }}>
          <h2>Verification status</h2>
          <p className={`pill ${status.cls}`}>{status.pill}</p>
          <p className="muted" style={{ marginTop: 12 }}>{status.text}</p>
          {profile.verification_status === "approved" && <p style={{ marginTop: 12 }}><Link to="/doctor/schedule">Set your schedule →</Link></p>}
          {user && <p className="muted" style={{ marginTop: 12 }}>Signed in as {user.phone}</p>}
        </div>
      </div>
    </div>
  );
}

export default function Onboarding() { return <RequireRole role="doctor"><Page /></RequireRole>; }
