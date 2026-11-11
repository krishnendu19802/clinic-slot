from django.db import models


class Channel(models.TextChoices):
    SMS = "sms"
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class NotificationStatus(models.TextChoices):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
