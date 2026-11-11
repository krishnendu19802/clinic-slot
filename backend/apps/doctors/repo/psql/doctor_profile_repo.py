from apps.doctors.models import DoctorProfile


class DoctorProfileRepo:
    def create_blank(self, *, user) -> DoctorProfile:
        return DoctorProfile.objects.create(user=user)

    def get_for_user(self, *, user) -> DoctorProfile:
        return DoctorProfile.objects.select_related("council").prefetch_related("specialities").get(user=user)

    def registration_taken(self, *, council, registration_no: str, exclude: DoctorProfile) -> bool:
        return DoctorProfile.objects.filter(council=council, registration_no=registration_no) \
            .exclude(pk=exclude.pk).exists()

    def set_name(self, *, profile: DoctorProfile, name: str) -> None:
        profile.full_name = name
        profile.save(update_fields=["full_name"])

    def update(self, *, profile: DoctorProfile, fields: dict, specialities: list | None) -> DoctorProfile:
        for key, value in fields.items():
            setattr(profile, key, value)
        profile.save()
        if specialities is not None:
            profile.specialities.set(specialities)
        return profile

    def set_status(self, *, profile: DoctorProfile, status: str, **extra) -> None:
        profile.verification_status = status
        for key, value in extra.items():
            setattr(profile, key, value)
        profile.save()
