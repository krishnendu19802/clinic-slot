from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.payments import views as payment_views
from apps.payments.models import Payment, ReconciliationIssue, Refund, WebhookEvent
from apps.scheduling.models import Slot

from .factories import make_doctor
from .helpers import login
from .test_booking_holds import DETAILS, hold, pick

pytestmark = pytest.mark.django_db
IST = ZoneInfo("Asia/Kolkata")
B = "/api/v1/bookings"
WEBHOOK = "/api/v1/webhooks/razorpay"


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


def to_payment(api, slot):
    """hold -> details -> pay; returns (booking_id, razorpay_order_id)."""
    bid = hold(api, slot).data["id"]
    assert api.patch(f"{B}/{bid}", DETAILS, format="json").status_code == 200
    order = api.post(f"{B}/{bid}/pay")
    assert order.status_code == 200
    return bid, order.data["razorpay_order_id"]


def verify(api, bid, order_id, payment_id="pay_1"):
    return api.post(f"{B}/{bid}/payment/verify", {"razorpay_order_id": order_id, "razorpay_payment_id": payment_id,
                                                  "razorpay_signature": "sig"}, format="json")


def lapse(bid, minutes_ago):
    past = timezone.now() - timedelta(minutes=minutes_ago)
    Booking.objects.filter(pk=bid).update(hold_expires_at=past)
    Slot.objects.filter(bookings__pk=bid).update(held_until=past)


def webhook(api, order_id, *, event="payment.captured", amount=50000, event_id="evt_1", payment_id="pay_1"):
    body = {"event": event, "payload": {"payment": {"entity": {"id": payment_id, "order_id": order_id,
                                                               "amount": amount, "method": "upi"}}}}
    return api.post(WEBHOOK, body, format="json", HTTP_X_RAZORPAY_EVENT_ID=event_id)


def test_pay_returns_server_priced_idempotent_order(p1, d1):
    bid = hold(p1, pick(d1[1])).data["id"]
    assert p1.post(f"{B}/{bid}/pay").data["error"]["code"] == "DETAILS_MISSING"
    p1.patch(f"{B}/{bid}", DETAILS, format="json")
    a, b = p1.post(f"{B}/{bid}/pay").data, p1.post(f"{B}/{bid}/pay").data
    assert a["razorpay_order_id"] == b["razorpay_order_id"]  # a Checkout retry reuses the open order
    assert a["amount_paise"] == 50000 and a["currency"] == "INR"
    assert a["prefill"] == {"name": "Asha Roy", "contact": "+919800012345"}


def test_pay_refused_after_hold_expiry(p1, d1):
    bid = hold(p1, pick(d1[1])).data["id"]
    p1.patch(f"{B}/{bid}", DETAILS, format="json")
    lapse(bid, 1)
    r = p1.post(f"{B}/{bid}/pay")
    assert r.status_code == 409 and r.data["error"]["code"] == "HOLD_EXPIRED"


def test_verify_confirms_the_booking_and_books_the_slot(p1, d1):
    slot = pick(d1[1])
    bid, order = to_payment(p1, slot)
    r = verify(p1, bid, order)
    assert r.status_code == 200
    assert r.data["status"] == "confirmed" and r.data["payment_status"] == "paid" and r.data["hold_expires_at"] is None
    slot.refresh_from_db()
    assert slot.status == "booked" and slot.held_by is None
    pay = Payment.objects.get()
    assert pay.status == "captured" and pay.signature_verified and pay.amount_paise == 50000
    assert p1.post(f"{B}/{bid}/pay").data["error"]["code"] == "INVALID_STATE"


def test_verify_twice_is_idempotent(p1, d1):
    bid, order = to_payment(p1, pick(d1[1]))
    verify(p1, bid, order)
    again = verify(p1, bid, order)
    assert again.status_code == 200 and again.data["status"] == "confirmed"
    assert Payment.objects.count() == 1 and Refund.objects.count() == 0


def test_verify_is_owner_and_order_scoped_and_checks_the_signature(p1, p2, d1, d2, monkeypatch):
    bid, order = to_payment(p1, pick(d1[1]))
    assert verify(p2, bid, order).status_code == 404
    other_bid, other_order = to_payment(p1, pick(d2[1], days=4))
    assert verify(p1, bid, other_order).status_code == 404  # an order from a different booking
    monkeypatch.setattr(payment_views.PaymentVerifyViewSet.service.gateway, "verify_payment", lambda **kw: False)
    r = verify(p1, bid, order)
    assert r.status_code == 400 and r.data["error"]["code"] == "SIGNATURE_INVALID"
    assert Booking.objects.get(pk=bid).status == "pending_payment" and other_bid


def test_webhook_confirms_even_if_the_browser_never_called_verify(p1, d1):
    from rest_framework.test import APIClient
    bid, order = to_payment(p1, pick(d1[1]))
    r = webhook(APIClient(), order)  # no JWT: Razorpay calls us
    assert r.status_code == 200
    assert Booking.objects.get(pk=bid).status == "confirmed"
    assert verify(p1, bid, order).data["status"] == "confirmed"  # the late verify is a no-op
    assert Payment.objects.count() == 1


def test_duplicate_webhook_event_is_ignored(p1, d1):
    from rest_framework.test import APIClient
    bid, order = to_payment(p1, pick(d1[1]))
    api = APIClient()
    assert webhook(api, order).status_code == 200 and webhook(api, order).status_code == 200
    assert WebhookEvent.objects.count() == 1 and Booking.objects.get(pk=bid).status == "confirmed"


def test_webhook_unknown_order_amount_mismatch_and_failure(p1, d1):
    from rest_framework.test import APIClient
    api = APIClient()
    assert webhook(api, "order_nope", event_id="e1").status_code == 200
    assert WebhookEvent.objects.get(razorpay_event_id="e1").error  # recorded, still a 200
    bid, order = to_payment(p1, pick(d1[1]))
    assert webhook(api, order, amount=100, event_id="e2").status_code == 200
    assert Booking.objects.get(pk=bid).status == "pending_payment"
    assert ReconciliationIssue.objects.get().kind == "amount_mismatch"
    assert webhook(api, order, event="payment.failed", event_id="e3", payment_id="pay_f").status_code == 200
    assert Payment.objects.get(razorpay_payment_id="pay_f").status == "failed"
    assert Booking.objects.get(pk=bid).status == "pending_payment"


def test_payment_inside_the_grace_window_still_confirms(p1, d1):
    bid, order = to_payment(p1, pick(d1[1]))
    lapse(bid, 1)  # hold ended a minute ago, grace is 2
    assert verify(p1, bid, order).data["status"] == "confirmed"


def test_payment_after_grace_is_refunded(p1, d1):
    slot = pick(d1[1])
    bid, order = to_payment(p1, slot)
    lapse(bid, 5)
    r = verify(p1, bid, order)
    assert r.status_code == 409 and r.data["error"]["code"] == "SLOT_LOST_REFUNDED"
    b = p1.get(f"{B}/{bid}").data
    assert b["status"] == "cancelled" and b["cancelled_by"] == "system" and b["cancel_reason"] == "slot_lost"
    assert b["refund"] == {"amount_paise": 50000, "status": "pending"} and b["payment_status"] == "refund_pending"
    refund = Refund.objects.get()
    assert refund.reason == "slot_conflict" and refund.amount_paise == 50000
    slot.refresh_from_db()
    assert slot.status == "available"
    assert verify(p1, bid, order).status_code == 409 and Refund.objects.count() == 1  # never a second refund


def test_payment_after_someone_else_took_the_slot_is_refunded_and_their_hold_is_untouched(p1, p2, d1):
    slot = pick(d1[1])
    bid, order = to_payment(p1, slot)
    lapse(bid, 1)
    other = hold(p2, slot)  # lazy expiry lets p2 in
    assert other.status_code == 201
    assert verify(p1, bid, order).data["error"]["code"] == "SLOT_LOST_REFUNDED"
    slot.refresh_from_db()
    assert slot.status == "held" and slot.held_by.phone == "+919810100002"


def test_payment_that_would_now_overlap_another_booking_is_refunded(p1, d1, d2):
    first = pick(d1[1])
    bid, order = to_payment(p1, first)
    lapse(bid, 1)
    assert hold(p1, pick(d2[1])).status_code == 201  # the lapsed hold no longer blocks the calendar
    assert verify(p1, bid, order).data["error"]["code"] == "SLOT_LOST_REFUNDED"
    first.refresh_from_db()
    assert first.status == "available"


def test_full_happy_path_through_the_api_and_django_admin(client):
    from rest_framework.test import APIClient

    from apps.doctors.models import Council, DoctorProfile, Speciality
    from tests.test_doctor_onboarding import pdf

    doc = login("doctor", "+919810400001")
    doc.patch("/api/v1/doctor/profile", {
        "full_name": "Dr A Sen", "gender": "male", "registration_no": "WBMC-77", "degrees": ["MBBS"],
        "council_id": Council.objects.first().pk, "specialities": [Speciality.objects.get(slug="dermatology").pk],
        "experience_years": 12, "fee_paise": 50000, "languages": ["English"]}, format="json")
    for t in ("registration", "degree", "id"):
        doc.post("/api/v1/doctor/documents", {"type": t, "file": pdf()}, format="multipart")
    clinic = doc.post("/api/v1/doctor/clinics", {
        "name": "Sample Clinic", "address": "City Centre", "area": "City Centre", "city": "Durgapur",
        "pincode": "713201", "lat": "23.52", "lng": "87.31"}, format="json").data["id"]
    doc.put(f"/api/v1/doctor/clinics/{clinic}/schedule",
            {"windows": [{"weekday": d, "start_time": "16:00", "end_time": "17:00"} for d in range(1, 8)]},
            format="json")
    assert doc.post("/api/v1/doctor/profile/submit").status_code == 200

    public = APIClient()
    assert public.get("/api/v1/doctors", {"speciality": "dermatology"}).data["items"] == []  # not live yet

    admin = User.objects.create_superuser(email="ops@example.com", password="pw")
    client.force_login(admin)
    pk = DoctorProfile.objects.get(user__phone="+919810400001").pk
    r = client.post("/admin/doctors/doctorprofile/", {"action": "approve", "_selected_action": [pk]}, follow=True)
    assert r.status_code == 200 and "slots generated" in r.content.decode()

    listing = public.get("/api/v1/doctors", {"speciality": "dermatology", "date": str(
        (timezone.now() + timedelta(days=3)).astimezone(IST).date())})
    item = listing.data["items"][0]
    assert item["doctor"]["name"] == "Dr A Sen" and item["availability"]["slots_left"] == 5
    slot_id = item["availability"]["preview_slots"][0]["slot_id"]

    patient = login("patient", "+919810400002")
    bid = patient.post(B, {"slot_id": slot_id}, format="json").data["id"]
    patient.patch(f"{B}/{bid}", DETAILS, format="json")
    order = patient.post(f"{B}/{bid}/pay").data
    confirmed = verify(patient, bid, order["razorpay_order_id"]).data
    assert confirmed["status"] == "confirmed" and confirmed["doctor"]["name"] == "Dr A Sen"
    assert [b["id"] for b in patient.get(B).data["items"]] == [bid]
    after = public.get("/api/v1/doctors", {"speciality": "dermatology", "date": str(
        (timezone.now() + timedelta(days=3)).astimezone(IST).date())})
    assert after.data["items"][0]["availability"]["slots_left"] == 4  # the booked slot is gone from the grid
    assert slot_id not in [s["slot_id"] for s in after.data["items"][0]["availability"]["preview_slots"]]
