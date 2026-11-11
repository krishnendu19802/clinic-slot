from rest_framework.exceptions import ValidationError

from apps.doctors.repo.psql.doctor_profile_repo import DoctorProfileRepo
from apps.doctors.repo.psql.document_repo import DocumentRepo
from apps.doctors.services.profile_service import ProfileService

MAX_BYTES = 5 * 1024 * 1024
ALLOWED = {"application/pdf", "image/jpeg", "image/png"}


class DocumentService:
    def __init__(self, documents=None, profiles=None):
        self.documents = documents or DocumentRepo()
        self.profiles = profiles or DoctorProfileRepo()
        self.guard = ProfileService(profiles=self.profiles, documents=self.documents)

    def list(self, *, user):
        return self.documents.list_for(doctor=self.profiles.get_for_user(user=user))

    def upload(self, *, user, doc_type: str, file):
        profile = self.profiles.get_for_user(user=user)
        self.guard.assert_editable(profile=profile)
        if file.size > MAX_BYTES:
            raise ValidationError({"file": ["Max 5 MB"]})
        if file.content_type not in ALLOWED:
            raise ValidationError({"file": ["PDF, JPG or PNG only"]})
        return self.documents.replace(doctor=profile, doc_type=doc_type, file=file, original_name=file.name,
                                      content_type=file.content_type, size_bytes=file.size)

    def delete(self, *, user, document_id: int) -> bool:
        profile = self.profiles.get_for_user(user=user)
        self.guard.assert_editable(profile=profile)
        document = self.documents.get_for(doctor=profile, document_id=document_id)
        if not document:
            return False
        self.documents.delete(document=document)
        return True
