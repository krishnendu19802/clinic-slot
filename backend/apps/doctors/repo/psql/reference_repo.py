from apps.doctors.models import Council, Speciality


class ReferenceRepo:
    def councils(self):
        return Council.objects.order_by("name")

    def specialities(self):
        return Speciality.objects.order_by("name")
