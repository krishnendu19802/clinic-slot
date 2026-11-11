from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStamped
from apps.scheduling.models import Slot

from .enums import OCCUPYING, BookingStatus, CancelledBy


class Booking(TimeStamped):
    slot = models.ForeignKey(Slot, related_name="bookings", on_delete=models.PROTECT)
    patient_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="bookings", on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=BookingStatus.choices, default=BookingStatus.PENDING_PAYMENT)
    # Snapshot of the details entered at booking time (self or family member).
    patient_name = models.CharField(max_length=120, blank=True)
    patient_age = models.PositiveSmallIntegerField(null=True, blank=True)
    patient_gender = models.CharField(max_length=8, blank=True)
    patient_phone = models.CharField(max_length=16, blank=True)
    reason = models.CharField(max_length=250, blank=True)
    is_self = models.BooleanField(default=True)
    fee_paise = models.PositiveIntegerField()  # snapshot at hold time
    platform_fee_paise = models.PositiveIntegerField(default=0)
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    reschedule_count = models.PositiveSmallIntegerField(default=0)
    cancelled_by = models.CharField(max_length=8, choices=CancelledBy.choices, blank=True)
    cancel_reason = models.CharField(max_length=250, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["slot"], condition=Q(status__in=[s.value for s in OCCUPYING]), name="one_active_booking_per_slot")]
        indexes = [models.Index(fields=["patient_user", "status"])]

    @property
    def ref(self) -> str:
        return f"CS-{self.pk:06d}"
