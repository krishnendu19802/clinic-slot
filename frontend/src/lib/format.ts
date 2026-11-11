const TZ = "Asia/Kolkata"; // clinics are in IST at launch; the API sends UTC

const fmt = (opts: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat("en-IN", { timeZone: TZ, ...opts });

export const rupees = (paise: number) => `₹${(paise / 100).toLocaleString("en-IN")}`;
export const time = (iso: string) => fmt({ hour: "numeric", minute: "2-digit", hour12: true }).format(new Date(iso)).toLowerCase();
export const dateLong = (iso: string) => fmt({ weekday: "short", day: "numeric", month: "short" }).format(new Date(iso));
export const dateTime = (iso: string) => `${dateLong(iso)}, ${time(iso)}`;

/** YYYY-MM-DD of an instant in clinic time. */
export const dayKey = (d: Date | string) => fmt({ year: "numeric", month: "2-digit", day: "2-digit" })
  .format(new Date(d)).split("/").reverse().join("-");

export const todayKey = () => dayKey(new Date());

/** "Today", "Tomorrow", else "Mon 19 Oct" for a YYYY-MM-DD clinic date. */
export function dayLabel(day: string, now = new Date()): string {
  const diff = Math.round((Date.parse(`${day}T00:00:00Z`) - Date.parse(`${dayKey(now)}T00:00:00Z`)) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  return fmt({ weekday: "short", day: "numeric", month: "short" }).format(new Date(`${day}T12:00:00+05:30`));
}

export const initials = (name: string) =>
  name.replace(/^dr\.?\s*/i, "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");

export const secondsLeft = (expiresAt: string, serverTime: string, fetchedAt: number, now = Date.now()) => {
  const offset = Date.parse(serverTime) - fetchedAt; // server clock minus local clock, measured at fetch time
  return Math.max(0, Math.floor((Date.parse(expiresAt) - (now + offset)) / 1000));
};

export const mmss = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

/** Download-able .ics text for "Add to calendar". */
export function ics(b: { ref: string; start: string; end: string; doctor: string; clinic: string; address: string }) {
  const z = (iso: string) => new Date(iso).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  return ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ClinicSlot//EN", "BEGIN:VEVENT", `UID:${b.ref}@clinicslot`,
    `DTSTAMP:${z(new Date().toISOString())}`, `DTSTART:${z(b.start)}`, `DTEND:${z(b.end)}`,
    `SUMMARY:Appointment with ${b.doctor}`, `LOCATION:${b.clinic}, ${b.address}`, "END:VEVENT", "END:VCALENDAR"].join("\r\n");
}

/** Add days to a YYYY-MM-DD clinic date (pure calendar arithmetic, no time zones involved). */
export const addDays = (day: string, n: number) => new Date(Date.parse(`${day}T00:00:00Z`) + n * 86_400_000).toISOString().slice(0, 10);

/** {weekday:'Mon', dom:'19'} for a YYYY-MM-DD date card. */
export function dayParts(day: string) {
  const d = new Date(`${day}T12:00:00+05:30`);
  return { weekday: fmt({ weekday: "short" }).format(d), dom: fmt({ day: "numeric" }).format(d) };
}

/** Slot start times for one window, e.g. ["4:00 pm", ...] (clinic-local "HH:MM" in, labels out). */
export function windowSlots(start: string, end: string, minutes: number): string[] {
  const [sh, sm] = start.split(":").map(Number), [eh, em] = end.split(":").map(Number);
  const out: string[] = [];
  for (let t = sh! * 60 + sm!; t + minutes <= eh! * 60 + em!; t += minutes) {
    const h = Math.floor(t / 60), m = t % 60;
    out.push(`${h % 12 || 12}:${String(m).padStart(2, "0")} ${h >= 12 ? "pm" : "am"}`);
  }
  return out;
}

/** null if the window is usable, else why not (mirrors the server's rules so errors show before saving). */
export function windowProblem(start: string, end: string, minutes: number): string | null {
  const span = (Number(end.slice(0, 2)) * 60 + Number(end.slice(3, 5))) - (Number(start.slice(0, 2)) * 60 + Number(start.slice(3, 5)));
  if (!(span > 0)) return "End time must be after start time";
  if (span % minutes) return `${minutes}-minute slots do not divide ${span} minutes evenly`;
  return null;
}
