from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.doctors.models import DoctorProfile
from apps.scheduling.models import Clinic, Slot

_n = 0


def _next() -> int:
    global _n
    _n += 1
    return _n


def make_user(role="patient") -> User:
    return User.objects.create_user(phone=f"+9198000{_next():05d}", role=role)


def make_slot() -> Slot:
    doc = DoctorProfile.objects.create(user=make_user("doctor"))
    clinic = Clinic.objects.create(doctor=doc, name="C", address="a", city="Durgapur", area="CC",
                                   pincode="713201", lat=23.5, lng=87.3)
    start = timezone.now() + timedelta(days=1)
    return Slot.objects.create(clinic=clinic, start_ts=start, end_ts=start + timedelta(minutes=12),
                               seq=1, window_total=5, token=1)


def make_booking(slot, status="pending_payment", patient=None) -> Booking:
    return Booking.objects.create(slot=slot, patient_user=patient or make_user(), status=status, fee_paise=50000)


def make_doctor(*, phone: str, name="Dr Test", fee=50000, exp=10, gender="male", languages=("English",),
                speciality="dermatology", lat="23.520000", lng="87.310000", area="City Centre", city="Durgapur",
                weekdays=range(1, 8), approved=True, start="16:00", end="17:00"):
    """Approved doctor with one clinic and generated slots (the realistic starting point for most tests)."""
    from datetime import time

    from apps.accounts.models import User
    from apps.doctors.models import Council, DoctorProfile, Speciality
    from apps.scheduling.models import ScheduleTemplate
    from apps.scheduling.services.slot_generation_service import SlotGenerationService

    user = User.objects.create_user(phone=phone, role="doctor")
    doctor = DoctorProfile.objects.create(
        user=user, full_name=name, gender=gender, registration_no=f"R-{phone}", council=Council.objects.first(),
        degrees=["MBBS"], experience_years=exp, fee_paise=fee, languages=list(languages),
        verification_status="approved" if approved else "draft")
    doctor.specialities.add(Speciality.objects.get(slug=speciality))
    clinic = Clinic.objects.create(doctor=doctor, name=f"{name} Clinic", address="Addr", city=city, area=area,
                                   pincode="713201", lat=lat, lng=lng)
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    for day in weekdays:
        ScheduleTemplate.objects.create(clinic=clinic, weekday=day, start_time=time(h1, m1),
                                        end_time=time(h2, m2), slot_minutes=12)
    SlotGenerationService().generate(clinic=clinic)
    return doctor, clinic
