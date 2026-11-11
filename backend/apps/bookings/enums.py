from django.db import models


class BookingStatus(models.TextChoices):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    ARRIVED = "arrived"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CancelledBy(models.TextChoices):
    PATIENT = "patient"
    DOCTOR = "doctor"
    SYSTEM = "system"


# Statuses that occupy a slot. The DB partial unique index is the double-booking guarantee.
OCCUPYING = [BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED, BookingStatus.ARRIVED,
             BookingStatus.COMPLETED, BookingStatus.NO_SHOW]
# Statuses that block the patient from other overlapping bookings.
ACTIVE = [BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED, BookingStatus.ARRIVED]
