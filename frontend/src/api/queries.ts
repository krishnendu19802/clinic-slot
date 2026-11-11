import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { Booking, Clinic, Council, DocItem, DoctorDetail, DoctorProfileData, DoctorSlot, GridDay, Page, Policy, ScheduleException, ScheduleWindow, SearchItem, Speciality } from "./types";

export const usePolicy = () => useQuery({ queryKey: ["policy"], queryFn: () => api<Policy>("/policy", { auth: false }), staleTime: 3_600_000 });
export const useSpecialities = () =>
  useQuery({ queryKey: ["specialities"], queryFn: () => api<{ items: Speciality[] }>("/specialities", { auth: false }).then((r) => r.items), staleTime: 3_600_000 });
export const useSearch = (params: Record<string, string>) =>
  useQuery({ queryKey: ["search", params], queryFn: () => api<Page<SearchItem>>("/doctors", { params, auth: false }) });
export const useDoctor = (id: string) =>
  useQuery({ queryKey: ["doctor", id], queryFn: () => api<DoctorDetail>(`/doctors/${id}`, { auth: false }) });
export const useGrid = (doctorId: string, clinicId: number | undefined, from: string) =>
  useQuery({
    queryKey: ["grid", doctorId, clinicId, from], enabled: clinicId !== undefined,
    // sent with the token when we have one, so held_by_me / overlaps_mine are personalised
    queryFn: () => api<{ days: GridDay[] }>(`/doctors/${doctorId}/slots`, { params: { clinic_id: clinicId, from, days: 7 } }).then((r) => r.days),
  });
export const useBooking = (id: string | undefined) =>
  useQuery({ queryKey: ["booking", id], enabled: !!id, queryFn: () => api<Booking>(`/bookings/${id}`) });
export const useBookings = (tab: string) =>
  useQuery({ queryKey: ["bookings", tab], queryFn: () => api<Page<Booking>>("/bookings", { params: { tab } }) });
export const useActiveHolds = (enabled: boolean) =>
  useQuery({ queryKey: ["holds"], enabled, refetchInterval: 60_000, queryFn: () => api<{ items: Booking[] }>("/bookings/active-holds").then((r) => r.items) });

// ---- doctor side ----
export const useCouncils = () =>
  useQuery({ queryKey: ["councils"], queryFn: () => api<{ items: Council[] }>("/councils", { auth: false }).then((r) => r.items), staleTime: 3_600_000 });
export const useDoctorProfile = () => useQuery({ queryKey: ["doctor-profile"], queryFn: () => api<DoctorProfileData>("/doctor/profile") });
export const useDoctorDocuments = () =>
  useQuery({ queryKey: ["doctor-docs"], queryFn: () => api<{ items: DocItem[] }>("/doctor/documents").then((r) => r.items) });
export const useClinics = () =>
  useQuery({ queryKey: ["clinics"], queryFn: () => api<{ items: Clinic[] }>("/doctor/clinics").then((r) => r.items) });
export const useSchedule = (clinicId: number | undefined) =>
  useQuery({
    queryKey: ["schedule", clinicId], enabled: clinicId !== undefined,
    queryFn: () => api<{ windows: ScheduleWindow[]; exceptions: ScheduleException[] }>(`/doctor/clinics/${clinicId}/schedule`),
  });
export const useDoctorSlots = (clinicId: number | undefined, date: string) =>
  useQuery({
    queryKey: ["doctor-slots", clinicId, date], enabled: clinicId !== undefined && !!date,
    queryFn: () => api<{ items: DoctorSlot[] }>(`/doctor/clinics/${clinicId}/slots`, { params: { date } }).then((r) => r.items),
  });
