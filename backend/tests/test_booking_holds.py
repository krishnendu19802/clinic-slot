from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.bookings.models import Booking
from apps.bookings.services.booking_service import BookingService
from apps.payments.models import Payment, PaymentOrder
from apps.scheduling.models import Slot

from .factories import make_booking, make_doctor
from .helpers import login

pytestmark = pytest.mark.django_db
B = "/api/v1/bookings"
DETAILS = {"patient": {"is_self": True, "name": "Asha Roy", "age": 34, "gender": "female", "phone": "98000 12345",
                       "reason": "rash"}}


def pick(clinic, n=0, days=2):
    return Slot.objects.filter(clinic=clinic, start_ts__gt=timezone.now() + timedelta(days=days)) \
        .order_by("start_ts")[n]


@pytest.fixture
def p1():
    return login("patient", "+919810100001")


@pytest.fixture
def p2():
    return login("patient", "+919810100002")


@pytest.fixture
def d1():
    return make_doctor(phone="+919810200001", name="Dr One", fee=50000)


@pytest.fixture
def d2():
    return make_doctor(phone="+919810200002", name="Dr Two", fee=40000)


def hold(api, slot):
    return api.post(B, {"slot_id": slot.pk}, format="json")


def test_hold_creates_pending_booking_and_holds_the_slot(p1, d1):
    slot = pick(d1[1])
    r = hold(p1, slot)
    assert r.status_code == 201
    b = r.data
    assert b["status"] == "pending_payment" and b["patient"] is None and b["fee_paise"] == 50000
    assert b["ref"].startswith("CS-") and b["token"] == slot.token and b["server_time"]
    assert 7 * 60 < (parse_datetime(b["hold_expires_at"]) - timezone.now()).total_seconds() <= 8 * 60
    slot.refresh_from_db()
    assert slot.status == "held" and slot.held_by.phone == "+919810100001"


def test_hold_is_idempotent_for_the_same_slot(p1, d1):
    slot = pick(d1[1])
    first = hold(p1, slot)
    again = hold(p1, slot)
    assert again.status_code == 200 and again.data["id"] == first.data["id"]
    assert Booking.objects.count() == 1


def test_second_patient_gets_slot_taken_with_alternatives(p1, p2, d1):
    slot = pick(d1[1])
    hold(p1, slot)
    r = hold(p2, slot)
    assert r.status_code == 409 and r.data["error"]["code"] == "SLOT_TAKEN"
    alts = r.data["error"]["details"]["alternatives"]
    assert 1 <= len(alts) <= 4 and slot.pk not in [a["id"] for a in alts]


def test_lapsed_hold_is_free_for_someone_else_without_a_sweeper(p1, p2, d1):
    slot = pick(d1[1])
    first = hold(p1, slot).data["id"]
    past = timezone.now() - timedelta(minutes=1)
    Booking.objects.filter(pk=first).update(hold_expires_at=past)
    Slot.objects.filter(pk=slot.pk).update(held_until=past)
    assert hold(p2, slot).status_code == 201
    assert Booking.objects.get(pk=first).status == "expired"


def test_too_close_to_start_is_refused(p1, d1):
    slot = pick(d1[1])
    Slot.objects.filter(pk=slot.pk).update(start_ts=timezone.now() + timedelta(minutes=10),
                                           end_ts=timezone.now() + timedelta(minutes=22))
    r = hold(p1, slot)
    assert r.status_code == 409 and r.data["error"]["code"] == "TOO_LATE"


def test_unapproved_doctors_slots_cannot_be_held(p1):
    _, clinic = make_doctor(phone="+919810200009", approved=False)
    assert Slot.objects.filter(clinic=clinic).count() == 0  # none generated, and a stray id is a 404
    assert p1.post(B, {"slot_id": 999999}, format="json").status_code == 404


def test_new_hold_with_same_doctor_replaces_the_old_one(p1, d1):
    a, b = pick(d1[1], 0, days=2), pick(d1[1], 0, days=4)
    first = hold(p1, a).data["id"]
    assert hold(p1, b).status_code == 201
    assert Booking.objects.get(pk=first).status == "expired"
    a.refresh_from_db()
    assert a.status == "available" and a.held_by is None
    assert [h["id"] for h in p1.get(f"{B}/active-holds").data["items"]] != [first]


def test_holds_with_different_doctors_coexist_when_they_do_not_overlap(p1, d1, d2):
    hold(p1, pick(d1[1], 0, days=2))
    r = hold(p1, pick(d2[1], 0, days=4))
    assert r.status_code == 201
    holds = p1.get(f"{B}/active-holds").data["items"]
    assert len(holds) == 2 and holds[0]["hold_expires_at"] <= holds[1]["hold_expires_at"]


def test_overlapping_hold_with_another_doctor_is_refused_and_names_the_conflict(p1, d1, d2):
    first = hold(p1, pick(d1[1])).data
    r = hold(p1, pick(d2[1]))  # same clock time, another doctor
    assert r.status_code == 409 and r.data["error"]["code"] == "BOOKING_OVERLAP"
    c = r.data["error"]["details"]["conflicting_booking"]
    assert c["id"] == first["id"] and c["doctor_name"] == "Dr One" and c["status"] == "pending_payment"
    assert Booking.objects.filter(status="pending_payment").count() == 1


def test_overlap_rule_also_covers_confirmed_bookings_but_not_lapsed_holds(p1, d1, d2):
    from apps.accounts.models import User
    user = User.objects.get(phone="+919810100001")
    confirmed = make_booking(pick(d1[1]), status="confirmed", patient=user)
    assert hold(p1, pick(d2[1])).status_code == 409
    Booking.objects.filter(pk=confirmed.pk).update(status="cancelled")
    stale = make_booking(pick(d1[1]), status="pending_payment", patient=user)
    Booking.objects.filter(pk=stale.pk).update(hold_expires_at=timezone.now() - timedelta(minutes=1))
    assert hold(p1, pick(d2[1])).status_code == 201  # an expired hold no longer blocks the calendar


def test_slot_grid_marks_my_hold_and_overlapping_slots(p1, d1, d2):
    slot = pick(d1[1])
    hold(p1, slot)
    day = str(slot.start_ts.astimezone(ZoneInfo("Asia/Kolkata")).date())

    def cell(doctor_clinic, target_start):
        doctor, clinic = doctor_clinic
        grid = p1.get(f"/api/v1/doctors/{doctor.pk}/slots", {"clinic_id": clinic.pk, "from": day, "days": 1}).data
        return next(s for w in grid["days"][0]["windows"] for s in w["slots"] if s["start"] == target_start)

    mine = cell(d1, slot.start_ts)
    assert mine["held_by_me"] and not mine["available"]
    other = cell(d2, slot.start_ts)
    assert other["overlaps_mine"] and other["available"] and not other["held_by_me"]


def test_details_are_saved_validated_and_owner_only(p1, p2, d1):
    b = hold(p1, pick(d1[1])).data["id"]
    r = p1.patch(f"{B}/{b}", DETAILS, format="json")
    assert r.status_code == 200 and r.data["patient"]["phone"] == "+919800012345" and r.data["patient"]["age"] == 34
    bad = p1.patch(f"{B}/{b}", {"patient": {**DETAILS["patient"], "gender": "x", "age": 300}}, format="json")
    assert bad.status_code == 400 and {"gender", "age"} <= set(bad.data["error"]["fields"]["patient"])
    assert p2.patch(f"{B}/{b}", DETAILS, format="json").status_code == 404
    assert p2.get(f"{B}/{b}").status_code == 404


def test_details_after_expiry_or_confirmation_are_refused(p1, d1):
    b = hold(p1, pick(d1[1])).data["id"]
    Booking.objects.filter(pk=b).update(hold_expires_at=timezone.now() - timedelta(seconds=1))
    r = p1.patch(f"{B}/{b}", DETAILS, format="json")
    assert r.status_code == 409 and r.data["error"]["code"] == "HOLD_EXPIRED"
    Booking.objects.filter(pk=b).update(status="confirmed")
    r = p1.patch(f"{B}/{b}", DETAILS, format="json")
    assert r.status_code == 409 and r.data["error"]["code"] == "INVALID_STATE"


def test_release_frees_the_slot_and_is_not_repeatable(p1, d1):
    slot = pick(d1[1])
    b = hold(p1, slot).data["id"]
    assert p1.post(f"{B}/{b}/release").status_code == 204
    slot.refresh_from_db()
    assert slot.status == "available" and Booking.objects.get(pk=b).status == "expired"
    assert p1.post(f"{B}/{b}/release").status_code == 409


def test_release_is_refused_while_a_payment_is_in_flight(p1, d1):
    b = hold(p1, pick(d1[1])).data["id"]
    order = PaymentOrder.objects.create(booking_id=b, razorpay_order_id="order_x", amount_paise=50000)
    Payment.objects.create(order=order, razorpay_payment_id="pay_x", status="captured", amount_paise=50000)
    r = p1.post(f"{B}/{b}/release")
    assert r.status_code == 409 and r.data["error"]["code"] == "PAYMENT_IN_PROGRESS"


def test_my_bookings_tabs(p1, d1):
    from apps.accounts.models import User
    user = User.objects.get(phone="+919810100001")
    clinic = d1[1]
    upcoming = make_booking(pick(clinic, 0, days=2), "confirmed", patient=user)
    cancelled = make_booking(pick(clinic, 0, days=4), "cancelled", patient=user)
    done = make_booking(pick(clinic, 0, days=6), "completed", patient=user)
    hold(p1, pick(clinic, 0, days=8))  # a live hold is in none of the tabs
    ids = lambda tab: [i["id"] for i in p1.get(B, {"tab": tab}).data["items"]]  # noqa: E731
    assert ids("upcoming") == [upcoming.pk] and ids("cancelled") == [cancelled.pk] and ids("past") == [done.pk]
    assert p1.get(B).data["total"] == 1  # default tab = upcoming


def test_patient_only(d1):
    doc = login("doctor", "+919810300001")
    assert doc.post(B, {"slot_id": 1}, format="json").status_code == 403


def test_sweeper_frees_holds_only_after_the_payment_grace(p1, d1):
    slot = pick(d1[1])
    b = hold(p1, slot).data["id"]
    Booking.objects.filter(pk=b).update(hold_expires_at=timezone.now() - timedelta(minutes=1))  # inside grace
    assert BookingService().sweep_expired() == 0
    Booking.objects.filter(pk=b).update(hold_expires_at=timezone.now() - timedelta(minutes=3))
    assert BookingService().sweep_expired() == 1
    slot.refresh_from_db()
    assert Booking.objects.get(pk=b).status == "expired" and slot.status == "available"


@pytest.mark.django_db(transaction=True)
def test_concurrent_holds_on_one_slot_have_exactly_one_winner(d1):
    slot = pick(d1[1])
    clients = [login("patient", f"+91981010{i:04d}") for i in range(6)]

    def attempt(api):
        try:
            return hold(api, slot).status_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(attempt, clients))
    assert sorted(codes) == [201] + [409] * 5
    assert Booking.objects.filter(slot=slot, status="pending_payment").count() == 1
