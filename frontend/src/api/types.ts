// Shapes from docs/api/contract.md (v1.2). Money is integer paise; times are ISO-8601 UTC.
export type Role = "patient" | "doctor";
export type Verification = "draft" | "submitted" | "info_requested" | "approved" | "rejected" | "suspended";

export interface User {
  id: number;
  role: Role;
  phone: string;
  email: string | null;
  name: string;
  profile_complete: boolean;
  doctor: { id: number; verification_status: Verification; status_reason: string } | null;
}

export interface Policy {
  hold_minutes: number;
  cutoff_minutes: number;
  free_cancel_hours: number;
  late_cancel_refund_percent: number;
  default_slot_minutes: number;
  text: string;
}

export interface Speciality { id: number; slug: string; name: string; blurb: string }
export interface Council { id: number; name: string }
export interface Page<T> { items: T[]; page: number; page_size: number; total: number }

export interface SearchItem {
  doctor: { id: number; name: string; degrees: string[]; experience_years: number; fee_paise: number; languages: string[]; verified: true };
  clinic: { id: number; name: string; address: string; area: string; city: string; distance_km: number | null };
  availability: {
    date: string;
    day_state: "open" | "full" | "off";
    slots_left: number;
    preview_slots: { slot_id: number; start: string }[];
    next_available_start: string | null;
  };
}

export interface ClinicInfo {
  id: number; name: string; address: string; area: string; city: string; pincode: string;
  lat: number; lng: number; phone: string; schedule_summary: string;
}
export interface DoctorDetail {
  doctor: {
    id: number; name: string; degrees: string[]; remarks: string; registration_no: string; council: string | null;
    specialities: { id: number; name: string }[]; experience_years: number; fee_paise: number; languages: string[];
    verified: true;
  };
  clinics: ClinicInfo[];
}

export interface GridSlot {
  id: number; start: string; end: string; seq: number; window_total: number; token: number;
  available: boolean; held_by_me: boolean; overlaps_mine: boolean;
}
export interface GridDay {
  date: string; weekday: number;
  windows: { start_time: string; end_time: string; slot_minutes: number; slots: GridSlot[] }[];
}

export type BookingStatus = "pending_payment" | "confirmed" | "arrived" | "completed" | "no_show" | "cancelled" | "expired";
export interface PatientDetails { is_self: boolean; name: string; age: number; gender: "male" | "female" | "other"; phone: string; reason: string }
export interface Booking {
  id: number; ref: string; status: BookingStatus; server_time: string; hold_expires_at: string | null; token: number;
  slot: { id: number; start: string; end: string; seq: number; window_total: number };
  doctor: { id: number; name: string };
  clinic: { id: number; name: string; address: string; area: string; city: string; lat: number; lng: number; phone: string };
  patient: PatientDetails | null;
  fee_paise: number;
  can_cancel: boolean;
  can_reschedule: boolean;
  reschedule_blocked_reason: { code: string; text: string } | null;
  payment_status: null | "paid" | "refund_pending" | "refunded";
  refund: { amount_paise: number; status: string } | null;
  cancelled_by: string;
  cancel_reason: string;
}

export interface PayOrder {
  razorpay_key_id: string; razorpay_order_id: string; amount_paise: number; currency: string;
  prefill: { name: string; contact: string };
}
