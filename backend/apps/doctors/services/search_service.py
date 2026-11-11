from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from apps.core import platform
from apps.core.exceptions import ApiError
from apps.doctors.repo.psql.search_repo import DoctorSearchRepo
from apps.scheduling.availability import is_open

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _clock(t) -> str:
    return f"{t.hour % 12 or 12}{f':{t.minute:02d}' if t.minute else ''}"


def schedule_summary(*, windows) -> str:
    """'Mon, Wed, Fri, 4 to 5 pm' (first window's hours; enough for a profile card)."""
    if not windows:
        return ""
    days = ", ".join(DAYS[d - 1] for d in sorted({w.weekday for w in windows}))
    first = windows[0]
    suffix = "pm" if first.end_time.hour >= 12 else "am"
    return f"{days}, {_clock(first.start_time)} to {_clock(first.end_time)} {suffix}"


class SearchService:
    def __init__(self, search=None):
        self.search = search or DoctorSearchRepo()
        self.tz = ZoneInfo(settings.TIME_ZONE)

    def _bounds(self, *, day: date) -> tuple[datetime, datetime]:
        start = datetime.combine(day, time.min, tzinfo=self.tz)
        return start, start + timedelta(days=1)

    def queryset(self, *, filters: dict, sort: str):
        now = timezone.now()
        earliest = now + timedelta(minutes=platform.get("booking_cutoff_minutes"))
        filters = dict(filters)
        if filters.pop("available_today", False) and not filters.get("date"):
            filters["date"] = now.astimezone(self.tz).date()
        if filters.get("date"):
            filters["day_range"] = self._bounds(day=filters["date"])
        return self.search.search(now=now, earliest=earliest, filters=filters, sort=sort)

    def results(self, *, clinics: list, day: date | None) -> list[dict]:
        """Attach per-clinic availability for one date (the filter date, else today) in a single slot query."""
        now = timezone.now()
        earliest = now + timedelta(minutes=platform.get("booking_cutoff_minutes"))
        day = day or now.astimezone(self.tz).date()
        start, end = self._bounds(day=day)
        by_clinic: dict[int, list] = {c.pk: [] for c in clinics}
        for slot in self.search.slots_between(clinic_ids=list(by_clinic), start=start, end=end):
            by_clinic[slot.clinic_id].append(slot)
        out = []
        for c in clinics:
            day_slots = by_clinic[c.pk]
            open_slots = [s for s in day_slots if is_open(slot=s, now=now, earliest=earliest)]
            state = "open" if open_slots else ("full" if day_slots else "off")
            d = c.doctor
            out.append({
                "doctor": {"id": d.pk, "name": d.full_name, "degrees": d.degrees,
                           "experience_years": d.experience_years, "fee_paise": d.fee_paise,
                           "languages": d.languages, "verified": True},
                "clinic": {"id": c.pk, "name": c.name, "address": c.address, "area": c.area, "city": c.city,
                           "distance_km": round(c.distance_km, 1) if getattr(c, "distance_km", None) is not None
                           else None},
                "availability": {"date": day, "day_state": state, "slots_left": len(open_slots),
                                 "preview_slots": [{"slot_id": s.pk, "start": s.start_ts} for s in open_slots[:4]],
                                 "next_available_start": c.next_available_start}})
        return out

    def detail(self, *, doctor_id: int) -> dict:
        d = self.search.doctor(doctor_id=doctor_id)
        if not d:
            raise ApiError("NOT_FOUND", "Doctor not found", status_code=404)
        clinics = list(self.search.clinics_of(doctor=d))
        windows = list(self.search.windows_of(clinic_ids=[c.pk for c in clinics]))
        return {
            "doctor": {"id": d.pk, "name": d.full_name, "degrees": d.degrees, "remarks": d.remarks,
                       "registration_no": d.registration_no, "council": d.council.name if d.council else None,
                       "specialities": [{"id": s.pk, "name": s.name} for s in d.specialities.all()],
                       "experience_years": d.experience_years, "fee_paise": d.fee_paise,
                       "languages": d.languages, "verified": True},
            "clinics": [{"id": c.pk, "name": c.name, "address": c.address, "area": c.area, "city": c.city,
                         "pincode": c.pincode, "lat": float(c.lat), "lng": float(c.lng), "phone": c.phone,
                         "schedule_summary": schedule_summary(windows=[w for w in windows if w.clinic_id == c.pk])}
                        for c in clinics]}
