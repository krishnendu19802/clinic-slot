from django.db import models


class OrderStatus(models.TextChoices):
    CREATED = "created"
    PAID = "paid"
    EXPIRED = "expired"


class PaymentStatus(models.TextChoices):
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"


class RefundReason(models.TextChoices):
    PATIENT_CANCEL = "patient_cancel"
    DOCTOR_CANCEL = "doctor_cancel"
    SLOT_CONFLICT = "slot_conflict"
    ADMIN_MANUAL = "admin_manual"
    SCHEDULE_CHANGE = "schedule_change"


class RefundStatus(models.TextChoices):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class IssueKind(models.TextChoices):
    PAID_NO_BOOKING = "paid_no_booking"
    BOOKING_NO_PAYMENT = "booking_no_payment"
    AMOUNT_MISMATCH = "amount_mismatch"
    REFUND_STUCK = "refund_stuck"


class IssueStatus(models.TextChoices):
    OPEN = "open"
    RESOLVED = "resolved"
