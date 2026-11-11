from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core import audit
from apps.core.exceptions import ApiError
from apps.doctors.enums import DocType, Verification
from apps.doctors.repo.psql.doctor_profile_repo import DoctorProfileRepo
from apps.doctors.repo.psql.document_repo import DocumentRepo
from apps.doctors.services.registry_service import RegistryService

EDITABLE = {Verification.DRAFT, Verification.INFO_REQUESTED, Verification.REJECTED}
REQUIRED = ["full_name", "gender", "registration_no", "council", "degrees", "experience_years", "fee_paise",
            "languages"]


class ProfileService:
    def __init__(self, profiles=None, documents=None, registry=None):
        self.profiles = profiles or DoctorProfileRepo()
        self.documents = documents or DocumentRepo()
        self.registry = registry or RegistryService()

    def assert_editable(self, *, profile) -> None:
        if profile.verification_status not in EDITABLE:
            raise ApiError("PROFILE_LOCKED", "Profile cannot be changed in its current status",
                           status=profile.verification_status)

    def get(self, *, user):
        return self.profiles.get_for_user(user=user)

    def update(self, *, user, fields: dict, specialities: list | None):
        profile = self.profiles.get_for_user(user=user)
        self.assert_editable(profile=profile)
        council = fields.get("council", profile.council)
        registration_no = fields.get("registration_no", profile.registration_no)
        if council and registration_no and self.profiles.registration_taken(
                council=council, registration_no=registration_no, exclude=profile):
            raise ValidationError({"registration_no": ["This registration number is already registered"]})
        return self.profiles.update(profile=profile, fields=fields, specialities=specialities)

    @transaction.atomic
    def submit(self, *, user):
        profile = self.profiles.get_for_user(user=user)
        self.assert_editable(profile=profile)
        missing = {f: ["This field is required"] for f in REQUIRED if not getattr(profile, f)}
        if not profile.specialities.exists():
            missing["specialities"] = ["Pick at least one speciality"]
        absent = {t.value for t in DocType} - self.documents.types_present(doctor=profile)
        for doc_type in sorted(absent):
            missing[f"document_{doc_type}"] = ["Upload this document"]
        if missing:
            raise ValidationError(missing)
        result = self.registry.check(registration_no=profile.registration_no, council_name=profile.council.name)
        self.profiles.set_status(profile=profile, status=Verification.SUBMITTED, registry_check=result,
                                 submitted_at=timezone.now(), status_reason="")
        audit.log(actor=user, action="doctor.submit", entity=profile, registry_check=result)
        return profile
