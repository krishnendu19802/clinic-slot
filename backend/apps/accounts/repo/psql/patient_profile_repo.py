from apps.accounts.models import PatientProfile, User


class PatientProfileRepo:
    def create_blank(self, *, user: User) -> PatientProfile:
        return PatientProfile.objects.create(user=user)

    def set_name(self, *, profile: PatientProfile, name: str) -> None:
        profile.full_name = name
        profile.save(update_fields=["full_name"])
