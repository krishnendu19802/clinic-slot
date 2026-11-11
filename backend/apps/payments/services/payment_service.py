"""Pay -> verify -> confirm. Verify and the webhook share one idempotent settle(); see docs/flow.md section 3."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.bookings.enums import BookingStatus, CancelledBy
from apps.bookings.repo.psql.booking_repo import BookingRepo
from apps.core import platform
from apps.core.exceptions import ApiError
from apps.payments.enums import IssueKind, OrderStatus, PaymentStatus, RefundReason
from apps.payments.gateway import PaymentGateway
from apps.payments.repo.psql.payment_repo import PaymentRepo
from apps.payments.repo.psql.webhook_repo import WebhookRepo
from apps.scheduling.repo.psql.slot_repo import SlotRepo

DONE = [BookingStatus.CONFIRMED, BookingStatus.ARRIVED, BookingStatus.COMPLETED, BookingStatus.NO_SHOW]


class PaymentService:
    def __init__(self, payments=None, bookings=None, slots=None, webhooks=None, gateway=None):
        self.payments = payments or PaymentRepo()
        self.bookings = bookings or BookingRepo()
        self.slots = slots or SlotRepo()
        self.webhooks = webhooks or WebhookRepo()
        self.gateway = gateway or PaymentGateway()

    # ---- create order ----------------------------------------------------------
    @staticmethod
    def _assert_payable(*, booking) -> None:
        if booking.status != BookingStatus.PENDING_PAYMENT:
            raise ApiError("INVALID_STATE", "Booking is not awaiting payment", status=booking.status)
        if booking.hold_expires_at <= timezone.now():
            raise ApiError("HOLD_EXPIRED", "Your hold on this slot has expired")
        if not booking.patient_name:
            raise ApiError("DETAILS_MISSING", "Enter the patient details before paying")

    def create_order(self, *, user, booking_id: int) -> dict:
        booking = self.bookings.get_for_patient(user=user, booking_id=booking_id)
        if not booking:
            raise ApiError("NOT_FOUND", "Booking not found", status_code=404)
        self._assert_payable(booking=booking)
        order = self.payments.open_order(booking=booking)  # idempotent: a Checkout retry reuses the open order
        if not order:
            razorpay_id = self.gateway.create_order(amount_paise=booking.fee_paise, receipt=booking.ref)
            with transaction.atomic():  # gateway call stays outside the lock
                locked = self.bookings.lock(booking_id=booking.pk)
                self._assert_payable(booking=locked)
                order = self.payments.create_order(booking=locked, razorpay_order_id=razorpay_id,
                                                   amount_paise=locked.fee_paise)
        return {"razorpay_key_id": settings.RAZORPAY_KEY_ID, "razorpay_order_id": order.razorpay_order_id,
                "amount_paise": order.amount_paise, "currency": order.currency,
                "prefill": {"name": booking.patient_name, "contact": booking.patient_phone}}

    # ---- verify ----------------------------------------------------------------
    def verify(self, *, user, booking_id: int, razorpay_order_id: str, razorpay_payment_id: str,
               razorpay_signature: str):
        booking = self.bookings.get_for_patient(user=user, booking_id=booking_id)
        order = self.payments.get_order(razorpay_order_id=razorpay_order_id)
        if not booking or not order or order.booking_id != booking.pk:
            raise ApiError("NOT_FOUND", "Booking or order not found", status_code=404)
        if not self.gateway.verify_payment(order_id=razorpay_order_id, payment_id=razorpay_payment_id,
                                           signature=razorpay_signature):
            raise ApiError("SIGNATURE_INVALID", "Payment signature could not be verified", status_code=400)
        outcome = self._settle(order=order, razorpay_payment_id=razorpay_payment_id, amount_paise=order.amount_paise,
                               method="", raw={}, verified=True)
        if outcome == "lost":  # committed first; the refund row exists by now
            raise ApiError("SLOT_LOST_REFUNDED", "The slot was no longer available; your payment will be refunded")
        return self.bookings.get_for_patient(user=user, booking_id=booking_id)

    # ---- the one place a booking becomes confirmed ------------------------------------
    @transaction.atomic
    def _settle(self, *, order, razorpay_payment_id: str, amount_paise: int, method: str, raw: dict,
                verified: bool) -> str:
        """Idempotent. Returns 'confirmed', 'already' or 'lost' (slot gone: refund recorded)."""
        booking = self.bookings.lock(booking_id=order.booking_id)
        payment = self.payments.upsert_payment(
            order=order, razorpay_payment_id=razorpay_payment_id, status=PaymentStatus.CAPTURED,
            amount_paise=amount_paise, method=method, signature_verified=verified, raw=raw)
        if booking.status in DONE:
            return "already"
        if payment.refunds.exists():
            return "lost"  # a repeated verify/webhook must not create a second refund
        now = timezone.now()
        self.payments.mark_order(order=order, status=OrderStatus.PAID)
        if booking.status == BookingStatus.PENDING_PAYMENT:
            grace = timedelta(minutes=platform.get("payment_grace_minutes"))
            lapsed = now > booking.hold_expires_at
            within = now <= booking.hold_expires_at + grace
            clash = lapsed and self.bookings.first_overlapping(
                user=booking.patient_user, start=booking.slot.start_ts, end=booking.slot.end_ts,
                exclude_ids=[booking.pk], now=now)
            if within and not clash:
                self.bookings.mark(booking=booking, status=BookingStatus.CONFIRMED, hold_expires_at=None)
                self.slots.mark_booked(slot=self.slots.lock(slot=booking.slot))
                return "confirmed"
            slot = self.slots.lock(slot=booking.slot)
            if slot.held_by_id == booking.patient_user_id and slot.status == "held":
                self.slots.release_hold(slot=slot)
        self.bookings.mark(booking=booking, status=BookingStatus.CANCELLED, cancelled_by=CancelledBy.SYSTEM,
                           cancel_reason="slot_lost", cancelled_at=now)
        self.payments.create_refund(payment=payment, booking=booking, amount_paise=amount_paise,
                                    reason=RefundReason.SLOT_CONFLICT)
        return "lost"

    # ---- webhook ---------------------------------------------------------------
    def handle_webhook(self, *, body: bytes, signature: str, event_id: str, payload: dict) -> str:
        """Store first (unique event id), then process. Always safe to call twice with the same event."""
        if not self.gateway.verify_webhook(body=body, signature=signature):
            raise ApiError("SIGNATURE_INVALID", "Bad webhook signature", status_code=400)
        event = self.webhooks.create_if_new(event_id=event_id, type=payload.get("event", ""), payload=payload)
        if event is None:
            return "duplicate"
        try:
            self._process(event_type=event.type, payload=payload)
            self.webhooks.finish(event=event)
        except Exception as exc:  # noqa: BLE001 - stored for reconciliation; Razorpay must still get a 200
            self.webhooks.finish(event=event, error=repr(exc))
        return "processed"

    def _process(self, *, event_type: str, payload: dict) -> None:
        if event_type not in ("payment.captured", "payment.failed"):
            return  # refund events arrive with the refund work
        entity = payload["payload"]["payment"]["entity"]
        order = self.payments.get_order(razorpay_order_id=entity["order_id"])
        if order is None:
            raise ApiError("NOT_FOUND", f"Unknown order {entity['order_id']}")
        if event_type == "payment.failed":
            self.payments.upsert_payment(order=order, razorpay_payment_id=entity["id"], status=PaymentStatus.FAILED,
                                         amount_paise=entity.get("amount", order.amount_paise),
                                         method=entity.get("method", ""), signature_verified=True, raw=entity)
            return
        if entity["amount"] != order.amount_paise:
            self.webhooks.add_issue(kind=IssueKind.AMOUNT_MISMATCH, booking=order.booking, payment=None,
                                    detail=f"order {order.amount_paise} vs captured {entity['amount']}")
            raise ApiError("AMOUNT_MISMATCH", "Captured amount differs from the order")
        self._settle(order=order, razorpay_payment_id=entity["id"], amount_paise=entity["amount"],
                     method=entity.get("method", ""), raw=entity, verified=True)
