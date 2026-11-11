from apps.doctors.models import DoctorDocument, DoctorProfile


class DocumentRepo:
    def list_for(self, *, doctor: DoctorProfile):
        return DoctorDocument.objects.filter(doctor=doctor).order_by("type")

    def get_for(self, *, doctor: DoctorProfile, document_id: int) -> DoctorDocument | None:
        return DoctorDocument.objects.filter(doctor=doctor, pk=document_id).first()

    def types_present(self, *, doctor: DoctorProfile) -> set[str]:
        return set(DoctorDocument.objects.filter(doctor=doctor).values_list("type", flat=True))

    def replace(self, *, doctor: DoctorProfile, doc_type: str, file, original_name: str, content_type: str,
                size_bytes: int) -> DoctorDocument:
        """One current document per type: the previous row and its file are removed."""
        for old in DoctorDocument.objects.filter(doctor=doctor, type=doc_type):
            old.file.delete(save=False)
            old.delete()
        return DoctorDocument.objects.create(doctor=doctor, type=doc_type, file=file, original_name=original_name,
                                             content_type=content_type, size_bytes=size_bytes)

    def delete(self, *, document: DoctorDocument) -> None:
        document.file.delete(save=False)
        document.delete()
