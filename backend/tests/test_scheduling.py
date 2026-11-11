from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.bookings.models import Booking
from apps.doctors.models import DoctorProfile
from apps.scheduling.models import Slot
from apps.scheduling.tasks import generate_slots

from .factories import make_booking
from .helpers import login

pytestmark = pytest.mark.django_db
URL = "/api/v1/doctor"
IST = ZoneInfo("Asia/Kolkata")
CLINIC = {"name": "Sample Clinic", "address": "City Centre", "area": "City Centre", "city": "Durgapur",
          "pincode": "713201", "lat": "23.520000", "lng": "87.310000"}


def win(weekday, start="16:00", end="17:00", **kw):
    return {"weekday": weekday, "start_time": start, "end_time": end, **kw}


@pytest.fixture
def doc():
    return login("doctor", "+919800066666")


def approve(phone="+919800066666"):
    DoctorProfile.objects.filter(user__phone=phone).update(verification_status="approved")


@pytest.fixture
def clinic(doc):
    return doc.post(f"{URL}/clinics", CLINIC, format="json").data["id"]


def put_schedule(doc, clinic, windows):
    return doc.put(f"{URL}/clinics/{clinic}/schedule", {"windows": windows}, format="json")


def all_weekdays(**kw):
    return [win(d, **kw) for d in range(1, 8)]


def test_slot_count_resolves_to_minutes_and_default_is_12(doc, clinic):
    r = put_schedule(doc, clinic, [win(1, slot_count=5), win(2)])
    assert r.status_code == 200
    got = doc.get(f"{URL}/clinics/{clinic}/schedule").data["windows"]
    assert [(w["weekday"], w["slot_minutes"], w["slot_count"]) for w in got] == [(1, 12, 5), (2, 12, 5)]
    assert got[0]["start_time"] == "16:00"


@pytest.mark.parametrize("windows", [
    [win(1, slot_count=7)],                                        # 7 does not divide 60
    [win(1, slot_minutes=25)],                                     # 25 does not divide 60
    [win(1, "17:00", "16:00")],                                    # end before start
    [win(1, "10:00", "13:00"), win(1, "12:00", "14:00")],          # overlap
])
def test_unusable_windows_are_rejected(doc, clinic, windows):
    r = put_schedule(doc, clinic, windows)
    assert r.status_code == 400 and r.data["error"]["code"] == "VALIDATION_ERROR"


def test_no_slots_until_doctor_is_approved_then_generated_on_horizon(doc, clinic):
    assert put_schedule(doc, clinic, all_weekdays()).data["slots_generated"] == 0
    approve()
    r = put_schedule(doc, clinic, all_weekdays())
    assert r.data["slots_generated"] >= 29 * 5  # ~30 days of 5 slots (today's may be past)
    slots = Slot.objects.filter(clinic_id=clinic).order_by("start_ts")
    s = slots.first()
    assert s.start_ts.astimezone(IST).hour == 16 and s.window_total == 5
    assert list(slots[:5].values_list("seq", flat=True)) == [1, 2, 3, 4, 5]
    assert slots.last().start_ts <= timezone.now() + timedelta(days=31)
    assert put_schedule(doc, clinic, all_weekdays()).data["slots_generated"] == 0  # idempotent


def test_two_windows_a_day_have_per_window_seq_and_day_wide_token(doc, clinic):
    approve()
    put_schedule(doc, clinic, [win(d, "10:00", "11:00") for d in range(1, 8)]
                 + [win(d, "16:00", "17:00") for d in range(1, 8)])
    day = (timezone.now() + timedelta(days=3)).astimezone(IST).date()  # a whole future day
    rows = [s for s in Slot.objects.filter(clinic_id=clinic).order_by("start_ts")
            if s.start_ts.astimezone(IST).date() == day]
    assert [s.seq for s in rows] == [1, 2, 3, 4, 5] * 2
    assert [s.window_total for s in rows] == [5] * 10
    assert [s.token for s in rows] == list(range(1, 11))


def test_blocking_a_day_removes_open_slots_and_keeps_booked_one_as_conflict(doc, clinic):
    approve()
    put_schedule(doc, clinic, all_weekdays())
    day = (timezone.now() + timedelta(days=5)).astimezone(IST).date()
    booked = Slot.objects.filter(clinic_id=clinic, start_ts__date__gte=day).order_by("start_ts") \
        .filter(start_ts__gt=timezone.now() + timedelta(days=4)).first()
    local_day = booked.start_ts.astimezone(IST).date()
    booking = make_booking(booked, status="confirmed")
    r = doc.post(f"{URL}/clinics/{clinic}/exceptions", {"date": str(local_day), "type": "blocked"}, format="json")
    assert r.status_code == 201
    assert [(c["booking_id"], c["reason"]) for c in r.data["conflicts"]] == [(booking.pk, "day_blocked")]
    left = [s for s in Slot.objects.filter(clinic_id=clinic) if s.start_ts.astimezone(IST).date() == local_day]
    assert [s.pk for s in left] == [booked.pk]  # only the booked slot survives, nothing overlaps it
    assert Booking.objects.get(pk=booking.pk).status == "confirmed"  # never cancelled silently


def test_removing_a_window_keeps_booked_slot_and_reports_it(doc, clinic):
    approve()
    put_schedule(doc, clinic, all_weekdays())
    booked = Slot.objects.filter(clinic_id=clinic, start_ts__gt=timezone.now() + timedelta(days=2)).first()
    make_booking(booked, status="confirmed")
    r = put_schedule(doc, clinic, [])
    assert [c["reason"] for c in r.data["conflicts"]] == ["window_removed"]
    assert list(Slot.objects.filter(clinic_id=clinic).values_list("pk", flat=True)) == [booked.pk]


def test_changing_slot_length_never_overlaps_a_kept_booking(doc, clinic):
    approve()
    put_schedule(doc, clinic, all_weekdays(slot_minutes=12))
    booked = Slot.objects.filter(clinic_id=clinic, start_ts__gt=timezone.now() + timedelta(days=2)).first()
    make_booking(booked, status="confirmed")
    r = put_schedule(doc, clinic, all_weekdays(slot_minutes=15))
    assert len(r.data["conflicts"]) == 1
    day = [s for s in Slot.objects.filter(clinic_id=clinic).order_by("start_ts")
           if s.start_ts.astimezone(IST).date() == booked.start_ts.astimezone(IST).date()]
    for a, b in zip(day, day[1:], strict=False):
        assert a.end_ts <= b.start_ts


def test_extra_window_and_partial_block(doc, clinic):
    approve()
    put_schedule(doc, clinic, [])
    day = str((timezone.now() + timedelta(days=3)).astimezone(IST).date())
    assert doc.post(f"{URL}/clinics/{clinic}/exceptions",
                    {"date": day, "type": "extra", "start_time": "10:00", "end_time": "11:00", "slot_minutes": 20},
                    format="json").data["slots_generated"] == 3
    r = doc.post(f"{URL}/clinics/{clinic}/exceptions",
                 {"date": day, "type": "blocked", "start_time": "10:20", "end_time": "10:40"}, format="json")
    assert r.status_code == 201 and Slot.objects.filter(clinic_id=clinic).count() == 2


def test_manual_block_and_unblock_and_booked_slot_refuses(doc, clinic):
    approve()
    put_schedule(doc, clinic, all_weekdays())
    a, b = Slot.objects.filter(clinic_id=clinic, start_ts__gt=timezone.now() + timedelta(days=2))[:2]
    assert doc.post(f"{URL}/slots/{a.pk}/block").status_code == 201
    assert Slot.objects.get(pk=a.pk).status == "blocked"
    assert doc.delete(f"{URL}/slots/{a.pk}/block").status_code == 204
    assert Slot.objects.get(pk=a.pk).status == "available"
    make_booking(b, status="confirmed")
    r = doc.post(f"{URL}/slots/{b.pk}/block")
    assert r.status_code == 409 and r.data["error"]["code"] == "HAS_BOOKING"


def test_owner_day_view_lists_every_status(doc, clinic):
    approve()
    put_schedule(doc, clinic, all_weekdays())
    s = Slot.objects.filter(clinic_id=clinic, start_ts__gt=timezone.now() + timedelta(days=2)).first()
    day = s.start_ts.astimezone(IST).date()
    doc.post(f"{URL}/slots/{s.pk}/block")
    r = doc.get(f"{URL}/clinics/{clinic}/slots", {"date": str(day)})
    assert [x["status"] for x in r.data["items"]] == ["blocked", "available", "available", "available", "available"]
    assert doc.get(f"{URL}/clinics/{clinic}/slots", {"date": "nope"}).status_code == 400


def test_clinic_with_future_booking_cannot_be_deleted(doc, clinic):
    approve()
    put_schedule(doc, clinic, all_weekdays())
    slot = Slot.objects.filter(clinic_id=clinic, start_ts__gt=timezone.now() + timedelta(days=2)).first()
    booking = make_booking(slot, status="confirmed")
    r = doc.delete(f"{URL}/clinics/{clinic}")
    assert r.status_code == 409 and r.data["error"]["code"] == "CLINIC_HAS_BOOKINGS"
    Booking.objects.filter(pk=booking.pk).update(status="cancelled")
    assert doc.delete(f"{URL}/clinics/{clinic}").status_code == 204
    assert doc.get(f"{URL}/clinics").data["items"] == []


def test_doctors_cannot_touch_each_others_clinics(doc, clinic):
    other = login("doctor", "+919800077777")
    assert other.get(f"{URL}/clinics/{clinic}/schedule").status_code == 404
    assert other.put(f"{URL}/clinics/{clinic}/schedule", {"windows": []}, format="json").status_code == 404
    assert other.patch(f"{URL}/clinics/{clinic}", {"name": "x"}, format="json").status_code == 404
    assert other.get(f"{URL}/clinics").data["items"] == []


def test_nightly_task_restores_the_horizon(doc, clinic):
    approve()
    put_schedule(doc, clinic, all_weekdays())
    total = Slot.objects.filter(clinic_id=clinic).count()
    Slot.objects.filter(clinic_id=clinic, start_ts__gt=timezone.now() + timedelta(days=10)).delete()
    assert generate_slots() > 0
    assert Slot.objects.filter(clinic_id=clinic).count() == total
    assert generate_slots() == 0
