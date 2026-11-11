from django.db import models


class ExceptionType(models.TextChoices):
    BLOCKED = "blocked"
    EXTRA = "extra"


class SlotStatus(models.TextChoices):
    AVAILABLE = "available"
    HELD = "held"
    BOOKED = "booked"
    BLOCKED = "blocked"
