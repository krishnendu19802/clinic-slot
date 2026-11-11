from datetime import datetime

from django.db.models import Q

from apps.accounts.models import User
from apps.bookings.enums import BookingStatus
from apps.bookings.models import Booking
from apps.scheduling.models import Slot

_JOINS = ("slot", "slot__clinic", "slot__clinic__doctor")


def _live(*, now: datetime) -> Q:
    """Bookings that currently block the patient's calendar: confirmed/arrived, or a hold still ticking."""
    return Q(status__in=[BookingStatus.CONFIRMED, BookingStatus.ARRIVED]) | Q(
        status=BookingStatus.PENDING_PAYMENT, hold_expires_at__gt=now)


class BookingRepo:
    def get_for_patient(self, *, user: User, booking_id: int) -> Booking | None:
        return (Booking.objects.select_related(*_JOINS).prefetch_related("orders__payments", "refunds")
                .filter(patient_user=user, pk=booking_id).first())

    def lock(self, *, booking_id: int) -> Booking | None:
        return Booking.objects.select_for_update().filter(pk=booking_id).first()

    def create(self, *, slot: Slot, user: User, fee_paise: int, hold_expires_at: datetime) -> Booking:
        return Booking.objects.create(slot=slot, patient_user=user, fee_paise=fee_paise,
                                      hold_expires_at=hold_expires_at)

    def holds(self, *, user: User, now: datetime):
        return (Booking.objects.select_related(*_JOINS).prefetch_related("orders__payments", "refunds")
                .filter(patient_user=user, status=BookingStatus.PENDING_PAYMENT, hold_expires_at__gt=now)
                .order_by("hold_expires_at"))

    def pending_with_doctor(self, *, user: User, doctor_id: int) -> list[Booking]:
        return list(Booking.objects.select_related("slot").filter(
            patient_user=user, status=BookingStatus.PENDING_PAYMENT, slot__clinic__doctor_id=doctor_id))

    def first_overlapping(self, *, user: User, start: datetime, end: datetime, exclude_ids: list[int],
                          now: datetime) -> Booking | None:
        return (Booking.objects.select_related(*_JOINS).filter(_live(now=now), patient_user=user,
                                                                slot__start_ts__lt=end, slot__end_ts__gt=start)
                .exclude(pk__in=exclude_ids).order_by("slot__start_ts").first())

    def active_ranges(self, *, user: User, start: datetime, end: datetime, now: datetime):
        return list(Booking.objects.filter(_live(now=now), patient_user=user, slot__start_ts__lt=end,
                                           slot__end_ts__gt=start).values_list("slot__start_ts", "slot__end_ts"))

    def expire_stale_on_slot(self, *, slot: Slot, now: datetime) -> None:
        """A lapsed hold still occupies the unique index; free it before someone else books the slot."""
        Booking.objects.filter(slot=slot, status=BookingStatus.PENDING_PAYMENT, hold_expires_at__lt=now) \
            .update(status=BookingStatus.EXPIRED)

    def stale_pending(self, *, before: datetime) -> list[Booking]:
        return list(Booking.objects.filter(status=BookingStatus.PENDING_PAYMENT, hold_expires_at__lt=before))

    def set_details(self, *, booking: Booking, name: str, age: int, gender: str, phone: str, reason: str,
                    is_self: bool) -> Booking:
        booking.patient_name, booking.patient_age, booking.patient_gender = name, age, gender
        booking.patient_phone, booking.reason, booking.is_self = phone, reason, is_self
        booking.save()
        return booking

    def mark(self, *, booking: Booking, **fields) -> Booking:
        for key, value in fields.items():
            setattr(booking, key, value)
        booking.save()
        return booking

    def list_for_patient(self, *, user: User, tab: str, now: datetime):
        qs = (Booking.objects.select_related(*_JOINS).prefetch_related("orders__payments", "refunds")
              .filter(patient_user=user))
        future, active = Q(slot__start_ts__gt=now), [BookingStatus.CONFIRMED, BookingStatus.ARRIVED]
        if tab == "upcoming":
            return qs.filter(status__in=active).filter(future).order_by("slot__start_ts")
        if tab == "past":
            done = Q(status__in=[BookingStatus.COMPLETED, BookingStatus.NO_SHOW])
            return qs.filter(done | (Q(status__in=active) & ~future)).order_by("-slot__start_ts")
        return qs.filter(status=BookingStatus.CANCELLED).order_by("-slot__start_ts")


