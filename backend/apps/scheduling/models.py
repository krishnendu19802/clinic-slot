from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.doctors.models import DoctorProfile

from .enums import ExceptionType, SlotStatus


class Clinic(models.Model):
    doctor = models.ForeignKey(DoctorProfile, related_name="clinics", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=250)
    city = models.CharField(max_length=60)
    area = models.CharField(max_length=60)
    pincode = models.CharField(max_length=10)
    phone = models.CharField(max_length=16, blank=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["city", "area"])]


class ScheduleTemplate(models.Model):
    """Weekly recurring window. weekday is ISO 1=Mon..7=Sun. Overlaps are rejected in the service layer."""

    clinic = models.ForeignKey(Clinic, related_name="windows", on_delete=models.CASCADE)
    weekday = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(end_time__gt=F("start_time")), name="window_end_after_start"),
            models.CheckConstraint(condition=Q(weekday__gte=1, weekday__lte=7), name="window_weekday_iso"),
        ]


class ScheduleException(models.Model):
    clinic = models.ForeignKey(Clinic, related_name="exceptions", on_delete=models.CASCADE)
    date = models.DateField()
    type = models.CharField(max_length=8, choices=ExceptionType.choices)
    start_time = models.TimeField(null=True, blank=True)  # null on `blocked` = whole day off
    end_time = models.TimeField(null=True, blank=True)
    slot_minutes = models.PositiveSmallIntegerField(null=True, blank=True)


class Slot(models.Model):
    clinic = models.ForeignKey(Clinic, related_name="slots", on_delete=models.CASCADE)
    start_ts = models.DateTimeField()
    end_ts = models.DateTimeField()
    seq = models.PositiveSmallIntegerField()  # position within window
    window_total = models.PositiveSmallIntegerField()
    token = models.PositiveSmallIntegerField()  # day-wide ordinal shown to patients
    status = models.CharField(max_length=10, choices=SlotStatus.choices, default=SlotStatus.AVAILABLE)
    held_until = models.DateTimeField(null=True, blank=True)
    held_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    capacity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["clinic", "start_ts"], name="uniq_slot_clinic_start"),
            models.CheckConstraint(condition=Q(end_ts__gt=F("start_ts")), name="slot_end_after_start"),
        ]
        indexes = [models.Index(fields=["start_ts"], condition=Q(status="available"), name="slot_open_start_idx")]
