from datetime import datetime

from django.db.models import Exists, F, FloatField, Min, OuterRef
from django.db.models.functions import ACos, Cast, Cos, Greatest, Least, Radians, Sin

from apps.doctors.enums import Verification
from apps.doctors.models import DoctorProfile
from apps.scheduling.availability import open_q
from apps.scheduling.models import Clinic, Slot

SORTS = {"earliest": ["next_available_start", "pk"], "experience": ["-doctor__experience_years", "pk"],
         "fee": ["doctor__fee_paise", "pk"], "distance": ["distance_km", "pk"]}


class DoctorSearchRepo:
    def approved_clinics(self):
        return Clinic.objects.filter(is_active=True, doctor__verification_status=Verification.APPROVED,
                                     doctor__user__is_active=True).select_related("doctor", "doctor__council")

    def search(self, *, now: datetime, earliest: datetime, filters: dict, sort: str):
        """Clinics of approved doctors that still have at least one bookable slot, annotated for ordering."""
        qs = self.approved_clinics().annotate(
            next_available_start=Min("slots__start_ts", filter=open_q(prefix="slots__", now=now, earliest=earliest)),
        ).filter(next_available_start__isnull=False)
        if v := filters.get("speciality"):
            qs = qs.filter(doctor__specialities__slug=v)
        if v := filters.get("city"):
            qs = qs.filter(city__iexact=v)
        if v := filters.get("area"):
            qs = qs.filter(area__icontains=v)
        if v := filters.get("pincode"):
            qs = qs.filter(pincode=v)
        if v := filters.get("fee_max"):
            qs = qs.filter(doctor__fee_paise__lte=v)
        if v := filters.get("experience_min"):
            qs = qs.filter(doctor__experience_years__gte=v)
        if v := filters.get("gender"):
            qs = qs.filter(doctor__gender=v)
        if v := filters.get("language"):
            qs = qs.filter(doctor__languages__contains=[v])
        if v := filters.get("day_range"):  # (start_utc, end_utc) of the requested date
            on_day = Slot.objects.filter(clinic=OuterRef("pk"), start_ts__gte=v[0], start_ts__lt=v[1]).filter(
                open_q(prefix="", now=now, earliest=earliest))
            qs = qs.filter(Exists(on_day))
        lat, lng = filters.get("lat"), filters.get("lng")
        if lat is not None and lng is not None:
            qs = qs.annotate(distance_km=self._haversine(lat=lat, lng=lng))
        elif sort == "distance":
            sort = "earliest"
        return qs.order_by(*SORTS[sort])

    @staticmethod
    def _haversine(*, lat: float, lng: float):
        clinic_lat, clinic_lng = Cast(F("lat"), FloatField()), Cast(F("lng"), FloatField())
        cosine = (Cos(Radians(lat)) * Cos(Radians(clinic_lat)) * Cos(Radians(clinic_lng) - Radians(lng))
                  + Sin(Radians(lat)) * Sin(Radians(clinic_lat)))
        return 6371.0 * ACos(Least(1.0, Greatest(-1.0, cosine)))  # clamp: float error can leave [-1, 1]

    def slots_between(self, *, clinic_ids: list[int], start: datetime, end: datetime):
        return Slot.objects.filter(clinic_id__in=clinic_ids, start_ts__gte=start, start_ts__lt=end).order_by("start_ts")

    def doctor(self, *, doctor_id: int) -> DoctorProfile | None:
        return (DoctorProfile.objects.filter(pk=doctor_id, verification_status=Verification.APPROVED,
                                             user__is_active=True)
                .select_related("council").prefetch_related("specialities").first())

    def clinics_of(self, *, doctor: DoctorProfile):
        return Clinic.objects.filter(doctor=doctor, is_active=True).order_by("id")

    def windows_of(self, *, clinic_ids: list[int]):
        from apps.scheduling.models import ScheduleTemplate
        return ScheduleTemplate.objects.filter(clinic_id__in=clinic_ids).order_by("weekday", "start_time")


