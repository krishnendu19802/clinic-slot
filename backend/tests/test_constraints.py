"""DB-level guarantees: these must hold even if every layer above has a bug."""
import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.bookings.models import Booking

from .factories import make_booking, make_slot

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("status", ["pending_payment", "confirmed", "arrived", "completed", "no_show"])
def test_second_occupying_booking_on_a_slot_is_rejected(status):
    slot = make_slot()
    make_booking(slot, status)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_booking(slot)


@pytest.mark.parametrize("status", ["cancelled", "expired"])
def test_cancelled_or_expired_booking_frees_the_slot(status):
    slot = make_slot()
    make_booking(slot, status)
    make_booking(slot)  # no error
    assert Booking.objects.filter(slot=slot).count() == 2


def test_patient_without_phone_is_rejected_but_staff_is_not():
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(email="x@example.com", role="patient")
    User.objects.create_superuser("admin@example.com", "pw")  # no phone, no role: fine
