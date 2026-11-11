from django.conf import settings
from django.db import models

from .enums import Channel, NotificationStatus


class Notification(models.Model):
    """Outbox: confirmations are sent sync after commit; failures and reminders are picked up by beat."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.CASCADE)
    channel = models.CharField(max_length=8, choices=Channel.choices)
    template = models.CharField(max_length=40)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=8, choices=NotificationStatus.choices, default=NotificationStatus.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)
    send_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "send_at"])]
