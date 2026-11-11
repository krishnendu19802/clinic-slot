"""Admin-side doctor decisions. Called by the Django admin actions (and any future API)."""
from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import ApiError
from apps.doctors.enums import Verification
from apps.doctors.repo.psql.doctor_profile_repo import DoctorProfileRepo
from apps.scheduling.repo.psql.clinic_repo import ClinicRepo
from apps.scheduling.services.slot_generation_service import SlotGenerationService


class VerificationService:
    def __init__(self, profiles=None, clinics=None, generator=None):
        self.profiles = profiles or DoctorProfileRepo()
        self.clinics = clinics or ClinicRepo()
        self.generator = generator or SlotGenerationService()

    @transaction.atomic
    def approve(self, *, profile, actor) -> int:
        """Go live: mark approved and generate slots for every clinic. Returns slots generated."""
        if profile.verification_status != Verification.SUBMITTED:
            raise ApiError("INVALID_STATE", "Only submitted profiles can be approved",
                           status=profile.verification_status)
        self.profiles.set_status(profile=profile, status=Verification.APPROVED, status_reason="",
                                 verified_at=timezone.now())
        generated = 0
        for clinic in self.clinics.list_for(doctor=profile):
            generated += self.generator.generate(clinic=self.clinics.lock(clinic=clinic)).generated
        audit.log(actor=actor, action="doctor.approve", entity=profile, slots_generated=generated)
        return generated
