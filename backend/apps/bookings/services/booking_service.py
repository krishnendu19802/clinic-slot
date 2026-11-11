from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.repo.psql.user_repo import UserRepo
from apps.bookings.enums import BookingStatus
from apps.core import platform
from apps.core.exceptions import ApiError
from apps.doctors.enums import Verification
from apps.payments.repo.psql.payment_repo import PaymentRepo
from apps.scheduling.availability import is_open
from apps.scheduling.repo.psql.slot_repo import SlotRepo

from ..repo.psql.booking_repo import BookingRepo

TABS = {"upcoming", "past", "cancelled"}


def slot_brief(slot) -> dict:
    return {"id": slot.pk, "start": slot.start_ts, "end": slot.end_ts, "seq": slot.seq,
            "window_total": slot.window_total, "token": slot.token, "available": True}


class BookingService:
    def __init__(self, bookings=None, slots=None, users=None, payments=None):
        self.bookings = bookings or BookingRepo()
        self.slots = slots or SlotRepo()
        self.users = users or UserRepo()
        self.payments = payments or PaymentRepo()

    # ---- reads -----------------------------------------------------------------
    def get(self, *, user, booking_id: int):
        booking = self.bookings.get_for_patient(user=user, booking_id=booking_id)
        if not booking:
            raise ApiError("NOT_FOUND", "Booking not found", status_code=404)
        return booking

    def holds(self, *, user):
        return self.bookings.holds(user=user, now=timezone.now())

    def list(self, *, user, tab: str):
        return self.bookings.list_for_patient(user=user, tab=tab if tab in TABS else "upcoming", now=timezone.now())

    # ---- hold ------------------------------------------------------------------
    @transaction.atomic
    def place_hold(self, *, user, slot_id: int):
        """Returns (booking, created). Idempotent for the same slot; see docs/flow.md section 3."""
        self.users.lock(user=user)
        slot = self.slots.lock_by_id(slot_id=slot_id)
        doctor = slot.clinic.doctor if slot else None
        if not slot or not slot.clinic.is_active or doctor.verification_status != Verification.APPROVED:
            raise ApiError("NOT_FOUND", "Slot not found", status_code=404)
        now = timezone.now()
        earliest = now + timedelta(minutes=platform.get("booking_cutoff_minutes"))
        if slot.start_ts <= earliest:
            raise ApiError("TOO_LATE", "This slot is too close to its start time to book")

        mine = self.bookings.pending_with_doctor(user=user, doctor_id=doctor.pk)
        same = next((b for b in mine if b.slot_id == slot.pk and b.hold_expires_at > now), None)
        if same:
            return self.get(user=user, booking_id=same.pk), False
        if not is_open(slot=slot, now=now, earliest=earliest):
            alternatives = self.slots.alternatives(slot=slot, now=now, earliest=earliest)
            raise ApiError("SLOT_TAKEN", "Someone just took this slot",
                           alternatives=[slot_brief(s) for s in alternatives])

        replaced = [b for b in mine if b.slot_id != slot.pk]  # one live hold per doctor: the older one makes way
        clash = self.bookings.first_overlapping(user=user, start=slot.start_ts, end=slot.end_ts,
                                                exclude_ids=[b.pk for b in replaced], now=now)
        if clash:
            raise ApiError("BOOKING_OVERLAP", "This time overlaps another booking of yours", conflicting_booking={
                "id": clash.pk, "ref": clash.ref, "status": clash.status,
                "doctor_name": clash.slot.clinic.doctor.full_name, "start": clash.slot.start_ts,
                "end": clash.slot.end_ts, "hold_expires_at": clash.hold_expires_at})

        for old in replaced:
            self._release(booking=old)
        self.bookings.expire_stale_on_slot(slot=slot, now=now)  # a lapsed hold row would block the unique index
        until = now + timedelta(minutes=platform.get("hold_minutes"))
        self.slots.mark_held(slot=slot, until=until, user=user)
        booking = self.bookings.create(slot=slot, user=user, fee_paise=doctor.fee_paise, hold_expires_at=until)
        return self.get(user=user, booking_id=booking.pk), True

    def _release(self, *, booking) -> None:
        """Expire a pending booking and free its slot if the slot is still held for it."""
        self.bookings.mark(booking=booking, status=BookingStatus.EXPIRED)
        self.payments.expire_open_orders(booking=booking)
        slot = self.slots.lock(slot=booking.slot)
        if slot.held_by_id == booking.patient_user_id and slot.status == "held":
            self.slots.release_hold(slot=slot)

    # ---- details / release -------------------------------------------------------
    def _own_pending(self, *, user, booking_id: int):
        booking = self.bookings.lock(booking_id=booking_id)
        if not booking or booking.patient_user_id != user.pk:
            raise ApiError("NOT_FOUND", "Booking not found", status_code=404)
        if booking.status != BookingStatus.PENDING_PAYMENT:
            raise ApiError("INVALID_STATE", "Booking is not awaiting payment", status=booking.status)
        return booking

    @transaction.atomic
    def update_details(self, *, user, booking_id: int, patient: dict):
        booking = self._own_pending(user=user, booking_id=booking_id)
        if booking.hold_expires_at <= timezone.now():
            raise ApiError("HOLD_EXPIRED", "Your hold on this slot has expired")
        self.bookings.set_details(booking=booking, reason=patient.get("reason", ""), **{
            k: patient[k] for k in ("name", "age", "gender", "phone", "is_self")})
        return self.get(user=user, booking_id=booking_id)

    @transaction.atomic
    def release(self, *, user, booking_id: int) -> None:
        booking = self._own_pending(user=user, booking_id=booking_id)
        if self.payments.has_live_payment(booking=booking):
            raise ApiError("PAYMENT_IN_PROGRESS", "A payment is already in progress for this booking")
        self._release(booking=booking)

    # ---- sweeper (Celery beat) -----------------------------------------------------
    def sweep_expired(self) -> int:
        """Free holds that lapsed beyond the payment grace. Lazy expiry already protects correctness."""
        cutoff = timezone.now() - timedelta(minutes=platform.get("payment_grace_minutes"))
        swept = 0
        for stale in self.bookings.stale_pending(before=cutoff):
            with transaction.atomic():
                booking = self.bookings.lock(booking_id=stale.pk)
                if booking.status == BookingStatus.PENDING_PAYMENT and not self.payments.has_live_payment(
                        booking=booking):
                    self._release(booking=booking)
                    swept += 1
        return swept
