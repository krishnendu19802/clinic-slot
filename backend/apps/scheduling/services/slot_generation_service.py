"""Turns weekly windows + date exceptions into concrete slot rows on a rolling horizon.

Never deletes or overlaps a slot that has an active booking: those are kept and reported as conflicts.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from apps.core import platform
from apps.doctors.enums import Verification
from apps.scheduling.enums import ExceptionType
from apps.scheduling.models import Clinic, Slot
from apps.scheduling.repo.psql.schedule_repo import ScheduleRepo
from apps.scheduling.repo.psql.slot_repo import SlotRepo


@dataclass
class GenerationResult:
    generated: int = 0
    conflicts: list[dict] = field(default_factory=list)


class SlotGenerationService:
    def __init__(self, schedule=None, slots=None):
        self.schedule = schedule or ScheduleRepo()
        self.slots = slots or SlotRepo()
        self.tz = ZoneInfo(settings.TIME_ZONE)

    def _desired(self, *, clinic: Clinic, today, horizon_days: int):
        """{start_utc: (end_utc, seq, window_total, token)} plus the set of fully blocked local dates."""
        by_weekday, by_date = defaultdict(list), defaultdict(list)
        for w in self.schedule.windows(clinic=clinic):
            by_weekday[w.weekday].append((w.start_time, w.end_time, w.slot_minutes))
        for e in self.schedule.exceptions(clinic=clinic):
            by_date[e.date].append(e)
        default_minutes = platform.get("default_slot_minutes")
        desired, blocked_days = {}, set()
        for offset in range(horizon_days):
            day = today + timedelta(days=offset)
            exceptions = by_date.get(day, [])
            if any(e.type == ExceptionType.BLOCKED and e.start_time is None for e in exceptions):
                blocked_days.add(day)
                continue
            windows = by_weekday[day.isoweekday()] + [
                (e.start_time, e.end_time, e.slot_minutes or default_minutes)
                for e in exceptions if e.type == ExceptionType.EXTRA]
            cuts = [(e.start_time, e.end_time) for e in exceptions
                    if e.type == ExceptionType.BLOCKED and e.start_time is not None]
            token = 0
            for start, end, minutes in sorted(windows):
                first = datetime.combine(day, start, tzinfo=self.tz)
                total = int((datetime.combine(day, end, tzinfo=self.tz) - first).total_seconds() // 60 // minutes)
                for i in range(total):
                    begin = first + timedelta(minutes=i * minutes)
                    token += 1
                    if any(a <= begin.timetz().replace(tzinfo=None) < b for a, b in cuts):
                        continue  # partially blocked: slot is skipped but still counted in numbering
                    desired[begin.astimezone(UTC)] = (begin.astimezone(UTC) + timedelta(minutes=minutes),
                                                      i + 1, total, token)
        return desired, blocked_days

    def generate(self, *, clinic: Clinic) -> GenerationResult:
        """Reconcile the clinic's future slots with its schedule. Call inside a transaction holding the clinic lock."""
        if clinic.doctor.verification_status != Verification.APPROVED:
            return GenerationResult()  # slots exist only for approved doctors
        now = timezone.now()
        horizon = platform.get("horizon_days")
        today = now.astimezone(self.tz).date()
        desired, blocked_days = self._desired(clinic=clinic, today=today, horizon_days=horizon)
        desired = {start: info for start, info in desired.items() if start > now}
        existing = self.slots.in_range(clinic=clinic, start=now, end=now + timedelta(days=horizon + 1))

        keep, drop, renumber = {}, [], []
        for slot in existing:
            info = desired.get(slot.start_ts)
            if info and info[0] == slot.end_ts:
                keep[slot.start_ts] = slot
                if not slot.has_booking and (slot.seq, slot.window_total, slot.token) != info[1:]:
                    slot.seq, slot.window_total, slot.token = info[1:]
                    renumber.append(slot)
            else:
                drop.append(slot)
        deleted = self.slots.delete_unbooked(slot_ids=[s.pk for s in drop])
        stuck = [s for s in drop if s.pk not in deleted]

        taken = [(s.start_ts, s.end_ts) for s in [*keep.values(), *stuck]]
        new = [Slot(clinic=clinic, start_ts=start, end_ts=end, seq=seq, window_total=total, token=token)
               for start, (end, seq, total, token) in desired.items()
               if start not in keep and not any(a < end and start < b for a, b in taken)]
        self.slots.create_many(slots=new)
        self.slots.renumber(slots=renumber)

        conflicts = []
        for booking in self.slots.bookings_on(slot_ids=[s.pk for s in stuck]):
            local_day = booking.slot.start_ts.astimezone(self.tz).date()
            conflicts.append({
                "booking_id": booking.pk, "ref": booking.ref, "patient_name": booking.patient_name,
                "start": booking.slot.start_ts, "clinic_id": clinic.pk,
                "reason": "day_blocked" if local_day in blocked_days else "window_removed"})
        return GenerationResult(generated=len(new), conflicts=conflicts)
