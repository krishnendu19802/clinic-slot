from apps.doctors.models import DoctorProfile


class DoctorProfileRepo:
    def create_blank(self, user) -> DoctorProfile:
        return DoctorProfile.objects.create(user=user)

    def set_name(self, profile: DoctorProfile, name: str) -> None:
        profile.full_name = name
        profile.save(update_fields=["full_name"])
