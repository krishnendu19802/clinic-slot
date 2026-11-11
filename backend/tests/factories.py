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
    return User.objects.create_user(f"+9198000{_next():05d}", role)


def make_slot() -> Slot:
    doc = DoctorProfile.objects.create(user=make_user("doctor"))
    clinic = Clinic.objects.create(doctor=doc, name="C", address="a", city="Durgapur", area="CC",
                                   pincode="713201", lat=23.5, lng=87.3)
    start = timezone.now() + timedelta(days=1)
    return Slot.objects.create(clinic=clinic, start_ts=start, end_ts=start + timedelta(minutes=12),
                               seq=1, window_total=5, token=1)


def make_booking(slot, status="pending_payment", patient=None) -> Booking:
    return Booking.objects.create(slot=slot, patient_user=patient or make_user(), status=status, fee_paise=50000)
