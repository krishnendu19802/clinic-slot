"""Doctor-side slot operations: day view and manual block/unblock."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction

from apps.core.exceptions import ApiError
from apps.scheduling.enums import SlotStatus
from apps.scheduling.repo.psql.clinic_repo import ClinicRepo
from apps.scheduling.repo.psql.slot_repo import SlotRepo


class SlotService:
    def __init__(self, clinics=None, slots=None):
        self.clinics = clinics or ClinicRepo()
        self.slots = slots or SlotRepo()
        self.tz = ZoneInfo(settings.TIME_ZONE)

    def day(self, *, user, clinic_id: int, date):
        clinic = self.clinics.get_for(doctor=user.doctor_profile, clinic_id=clinic_id)
        if not clinic:
            raise ApiError("NOT_FOUND", "Clinic not found", status_code=404)
        start = datetime.combine(date, time.min, tzinfo=self.tz)
        return self.slots.for_day(clinic=clinic, start=start, end=start + timedelta(days=1))

    def _own(self, *, user, slot_id: int):
        slot = self.slots.get_for_doctor(doctor=user.doctor_profile, slot_id=slot_id)
        if not slot:
            raise ApiError("NOT_FOUND", "Slot not found", status_code=404)
        return slot

    @transaction.atomic
    def block(self, *, user, slot_id: int):
        slot = self.slots.lock(slot=self._own(user=user, slot_id=slot_id))
        if slot.status == SlotStatus.BLOCKED:
            return slot
        if self.slots.has_occupying_booking(slot=slot):
            raise ApiError("HAS_BOOKING", "Cancel or move the booking first")
        return self.slots.set_status(slot=slot, status=SlotStatus.BLOCKED)

    @transaction.atomic
    def unblock(self, *, user, slot_id: int):
        slot = self.slots.lock(slot=self._own(user=user, slot_id=slot_id))
        if slot.status == SlotStatus.BLOCKED:
            self.slots.set_status(slot=slot, status=SlotStatus.AVAILABLE)
