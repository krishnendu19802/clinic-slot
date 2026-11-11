from django.utils import timezone

from apps.bookings.enums import OCCUPYING
from apps.doctors.enums import Verification
from apps.scheduling.models import Clinic


class ClinicRepo:
    def list_for(self, *, doctor):
        return Clinic.objects.filter(doctor=doctor, is_active=True).order_by("id")

    def get_for(self, *, doctor, clinic_id: int) -> Clinic | None:
        return Clinic.objects.filter(doctor=doctor, pk=clinic_id, is_active=True).first()

    def lock(self, *, clinic: Clinic) -> Clinic:
        """Serialise schedule edits and slot generation for one clinic (call inside a transaction)."""
        return Clinic.objects.select_for_update().select_related("doctor").get(pk=clinic.pk)

    def create(self, *, doctor, fields: dict) -> Clinic:
        return Clinic.objects.create(doctor=doctor, **fields)

    def update(self, *, clinic: Clinic, fields: dict) -> Clinic:
        for key, value in fields.items():
            setattr(clinic, key, value)
        clinic.save()
        return clinic

    def deactivate(self, *, clinic: Clinic) -> None:
        clinic.is_active = False
        clinic.save(update_fields=["is_active"])

    def has_future_bookings(self, *, clinic: Clinic) -> bool:
        return clinic.slots.filter(start_ts__gt=timezone.now(), bookings__status__in=OCCUPYING).exists()

    def approved_active(self):
        return Clinic.objects.filter(is_active=True, doctor__verification_status=Verification.APPROVED)
