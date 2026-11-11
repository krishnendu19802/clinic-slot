from django.db import transaction

from apps.core.exceptions import ApiError
from apps.scheduling.repo.psql.clinic_repo import ClinicRepo
from apps.scheduling.services.slot_generation_service import SlotGenerationService


class ClinicService:
    def __init__(self, clinics=None, generator=None):
        self.clinics = clinics or ClinicRepo()
        self.generator = generator or SlotGenerationService()

    def list(self, *, user):
        return self.clinics.list_for(doctor=user.doctor_profile)

    def _get(self, *, user, clinic_id: int):
        clinic = self.clinics.get_for(doctor=user.doctor_profile, clinic_id=clinic_id)
        if not clinic:
            raise ApiError("NOT_FOUND", "Clinic not found", status_code=404)
        return clinic

    def create(self, *, user, fields: dict):
        return self.clinics.create(doctor=user.doctor_profile, fields=fields)

    def update(self, *, user, clinic_id: int, fields: dict):
        return self.clinics.update(clinic=self._get(user=user, clinic_id=clinic_id), fields=fields)

    @transaction.atomic
    def delete(self, *, user, clinic_id: int) -> None:
        clinic = self.clinics.lock(clinic=self._get(user=user, clinic_id=clinic_id))
        if self.clinics.has_future_bookings(clinic=clinic):
            raise ApiError("CLINIC_HAS_BOOKINGS", "Resolve upcoming bookings before removing this clinic")
        self.clinics.deactivate(clinic=clinic)
