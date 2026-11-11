"""Public slot grid for one doctor clinic, personalised (held_by_me, overlaps_mine) when a patient is logged in."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from apps.bookings.repo.psql.booking_repo import BookingRepo
from apps.core import platform
from apps.core.exceptions import ApiError
from apps.doctors.repo.psql.search_repo import DoctorSearchRepo
from apps.scheduling.availability import is_open
from apps.scheduling.enums import SlotStatus
from apps.scheduling.repo.psql.slot_repo import SlotRepo

MAX_DAYS = 14


class AvailabilityService:
    def __init__(self, search=None, slots=None, bookings=None):
        self.search = search or DoctorSearchRepo()
        self.slots = slots or SlotRepo()
        self.bookings = bookings or BookingRepo()
        self.tz = ZoneInfo(settings.TIME_ZONE)

    def grid(self, *, doctor_id: int, clinic_id: int, start_date: date, days: int, viewer) -> dict:
        doctor = self.search.doctor(doctor_id=doctor_id)
        clinic = next((c for c in self.search.clinics_of(doctor=doctor) if c.pk == clinic_id), None) if doctor else None
        if not clinic:
            raise ApiError("NOT_FOUND", "Clinic not found", status_code=404)
        days = max(1, min(days, MAX_DAYS))
        start = datetime.combine(start_date, time.min, tzinfo=self.tz)
        end = start + timedelta(days=days)
        now = timezone.now()
        earliest = now + timedelta(minutes=platform.get("booking_cutoff_minutes"))
        mine = (self.bookings.active_ranges(user=viewer, start=start, end=end, now=now)
                if viewer and viewer.is_authenticated else [])
        by_day: dict[date, list] = {start_date + timedelta(days=i): [] for i in range(days)}
        for slot in self.slots.for_day(clinic=clinic, start=start, end=end):
            by_day[slot.start_ts.astimezone(self.tz).date()].append(slot)
        return {"days": [{"date": d, "weekday": d.isoweekday(),
                          "windows": self._windows(slots=slots, now=now, earliest=earliest, viewer=viewer, mine=mine)}
                         for d, slots in by_day.items()]}

    def _windows(self, *, slots: list, now, earliest, viewer, mine) -> list[dict]:
        windows: list[list] = []
        for slot in slots:  # seq restarts at 1 for each window
            if slot.seq == 1 or not windows:
                windows.append([])
            windows[-1].append(slot)
        out = []
        for group in windows:
            first, last = group[0], group[-1]
            out.append({
                "start_time": first.start_ts.astimezone(self.tz).strftime("%H:%M"),
                "end_time": last.end_ts.astimezone(self.tz).strftime("%H:%M"),
                "slot_minutes": int((first.end_ts - first.start_ts).total_seconds() // 60),
                "slots": [{
                    "id": s.pk, "start": s.start_ts, "end": s.end_ts, "seq": s.seq, "window_total": s.window_total,
                    "token": s.token, "available": is_open(slot=s, now=now, earliest=earliest),
                    "held_by_me": bool(viewer and s.status == SlotStatus.HELD and s.held_by_id == viewer.pk
                                       and s.held_until and s.held_until > now),
                    "overlaps_mine": any(a < s.end_ts and s.start_ts < b for a, b in mine),
                } for s in group]})
        return out
