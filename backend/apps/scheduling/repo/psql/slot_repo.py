from datetime import datetime

from django.db.models import Exists, OuterRef

from apps.bookings.enums import OCCUPYING
from apps.bookings.models import Booking
from apps.scheduling.availability import open_q
from apps.scheduling.enums import SlotStatus
from apps.scheduling.models import Clinic, Slot


class SlotRepo:
    def in_range(self, *, clinic: Clinic, start: datetime, end: datetime) -> list[Slot]:
        has_booking = Booking.objects.filter(slot=OuterRef("pk"), status__in=OCCUPYING)
        return list(Slot.objects.filter(clinic=clinic, start_ts__gt=start, start_ts__lt=end)
                    .annotate(has_booking=Exists(has_booking)))

    def create_many(self, *, slots: list[Slot]) -> None:
        Slot.objects.bulk_create(slots)

    def renumber(self, *, slots: list[Slot]) -> None:
        Slot.objects.bulk_update(slots, ["seq", "window_total", "token"])

    def delete_unbooked(self, *, slot_ids: list[int]) -> set[int]:
        """Lock the rows, re-check for bookings that raced in, delete the rest. Returns deleted ids."""
        locked = Slot.objects.select_for_update().filter(pk__in=slot_ids)
        booked = set(Booking.objects.filter(slot__in=locked, status__in=OCCUPYING).values_list("slot_id", flat=True))
        doomed = [s.pk for s in locked if s.pk not in booked]
        Slot.objects.filter(pk__in=doomed).delete()
        return set(doomed)

    def bookings_on(self, *, slot_ids: list[int]):
        return (Booking.objects.filter(slot_id__in=slot_ids, status__in=OCCUPYING)
                .select_related("slot", "patient_user"))

    def for_day(self, *, clinic: Clinic, start: datetime, end: datetime):
        return Slot.objects.filter(clinic=clinic, start_ts__gte=start, start_ts__lt=end).order_by("start_ts")

    def get_for_doctor(self, *, doctor, slot_id: int) -> Slot | None:
        return Slot.objects.select_related("clinic").filter(clinic__doctor=doctor, pk=slot_id).first()

    def lock(self, *, slot: Slot) -> Slot:
        return Slot.objects.select_for_update().get(pk=slot.pk)

    def has_occupying_booking(self, *, slot: Slot) -> bool:
        return Booking.objects.filter(slot=slot, status__in=OCCUPYING).exists()

    def set_status(self, *, slot: Slot, status: str) -> Slot:
        slot.status = status
        slot.held_until = None if status != SlotStatus.HELD else slot.held_until
        slot.save(update_fields=["status", "held_until"])
        return slot

    def lock_by_id(self, *, slot_id: int) -> Slot | None:
        return (Slot.objects.select_for_update(of=("self",)).select_related("clinic__doctor")
                .filter(pk=slot_id).first())

    def mark_held(self, *, slot: Slot, until: datetime, user) -> None:
        slot.status, slot.held_until, slot.held_by = SlotStatus.HELD, until, user
        slot.save(update_fields=["status", "held_until", "held_by"])

    def release_hold(self, *, slot: Slot) -> None:
        slot.status, slot.held_until, slot.held_by = SlotStatus.AVAILABLE, None, None
        slot.save(update_fields=["status", "held_until", "held_by"])

    def mark_booked(self, *, slot: Slot) -> None:
        slot.status, slot.held_until, slot.held_by = SlotStatus.BOOKED, None, None
        slot.save(update_fields=["status", "held_until", "held_by"])

    def alternatives(self, *, slot: Slot, now: datetime, earliest: datetime, limit: int = 4) -> list[Slot]:
        """Nearest bookable slots of the same clinic after this one."""
        return list(Slot.objects.filter(open_q(prefix="", now=now, earliest=earliest), clinic=slot.clinic,
                                        start_ts__gt=slot.start_ts).order_by("start_ts")[:limit])
