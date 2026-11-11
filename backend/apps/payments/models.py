from django.conf import settings
from django.db import models

from apps.bookings.models import Booking
from apps.core.models import TimeStamped

from .enums import IssueKind, IssueStatus, OrderStatus, PaymentStatus, RefundReason, RefundStatus


class PaymentOrder(TimeStamped):
    """One Razorpay order per payment attempt. Amount is copied from the booking, never from the client."""

    booking = models.ForeignKey(Booking, related_name="orders", on_delete=models.PROTECT)
    razorpay_order_id = models.CharField(max_length=40, unique=True)
    amount_paise = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=8, choices=OrderStatus.choices, default=OrderStatus.CREATED)


class Payment(TimeStamped):
    order = models.ForeignKey(PaymentOrder, related_name="payments", on_delete=models.PROTECT)
    razorpay_payment_id = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=10, choices=PaymentStatus.choices)
    amount_paise = models.PositiveIntegerField()
    method = models.CharField(max_length=20, blank=True)
    signature_verified = models.BooleanField(default=False)
    raw = models.JSONField(default=dict, blank=True)


class Refund(TimeStamped):
    payment = models.ForeignKey(Payment, related_name="refunds", on_delete=models.PROTECT)
    booking = models.ForeignKey(Booking, related_name="refunds", on_delete=models.PROTECT)
    razorpay_refund_id = models.CharField(max_length=40, unique=True, null=True, blank=True)
    amount_paise = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=RefundReason.choices)
    status = models.CharField(max_length=10, choices=RefundStatus.choices, default=RefundStatus.PENDING)
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)


class WebhookEvent(models.Model):
    """Insert-first (unique event id) gives idempotency and doubles as the payment audit trail."""

    razorpay_event_id = models.CharField(max_length=60, unique=True)
    type = models.CharField(max_length=40)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)


class ReconciliationIssue(TimeStamped):
    kind = models.CharField(max_length=20, choices=IssueKind.choices)
    booking = models.ForeignKey(Booking, null=True, blank=True, on_delete=models.SET_NULL)
    payment = models.ForeignKey(Payment, null=True, blank=True, on_delete=models.SET_NULL)
    detail = models.TextField(blank=True)
    status = models.CharField(max_length=8, choices=IssueStatus.choices, default=IssueStatus.OPEN)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    resolved_at = models.DateTimeField(null=True, blank=True)
