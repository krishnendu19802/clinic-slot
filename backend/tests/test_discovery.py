from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.scheduling.models import Slot

from .factories import make_doctor

pytestmark = pytest.mark.django_db
IST = ZoneInfo("Asia/Kolkata")
SEARCH = "/api/v1/doctors"


@pytest.fixture
def api():
    return APIClient()


def names(r):
    return [i["doctor"]["name"] for i in r.data["items"]]


def future_day(n=3):
    return str((timezone.now() + timedelta(days=n)).astimezone(IST).date())


def test_policy_is_public_and_states_the_rule(api):
    r = api.get("/api/v1/policy")
    assert r.status_code == 200 and r.data["hold_minutes"] == 8 and "4 hours" in r.data["text"]


def test_only_approved_doctors_with_open_slots_are_listed(api):
    make_doctor(phone="+919810000001", name="Live")
    make_doctor(phone="+919810000002", name="Pending", approved=False)
    _, closed = make_doctor(phone="+919810000003", name="Blocked all")
    Slot.objects.filter(clinic=closed).update(status="blocked")
    r = api.get(SEARCH)
    assert r.status_code == 200 and names(r) == ["Live"]
    assert {"items", "page", "page_size", "total"} <= set(r.data)


def test_filters(api):
    make_doctor(phone="+919810000011", name="A", fee=30000, exp=5, gender="female", languages=["Bengali"],
                speciality="paediatrics", area="Bidhannagar")
    make_doctor(phone="+919810000012", name="B", fee=70000, exp=20, gender="male", languages=["English", "Hindi"])
    assert names(api.get(SEARCH, {"speciality": "paediatrics"})) == ["A"]
    assert names(api.get(SEARCH, {"fee_max": 40000})) == ["A"]
    assert names(api.get(SEARCH, {"experience_min": 10})) == ["B"]
    assert names(api.get(SEARCH, {"gender": "female"})) == ["A"]
    assert names(api.get(SEARCH, {"language": "Hindi"})) == ["B"]
    assert names(api.get(SEARCH, {"area": "bidhan"})) == ["A"]
    assert api.get(SEARCH, {"gender": "nonsense"}).status_code == 400


def test_sorting_and_distance(api):
    make_doctor(phone="+919810000021", name="Far", fee=10000, exp=1, lat="22.500000", lng="88.300000")
    make_doctor(phone="+919810000022", name="Near", fee=90000, exp=30, lat="23.520100", lng="87.310100")
    assert names(api.get(SEARCH, {"sort": "fee"})) == ["Far", "Near"]
    assert names(api.get(SEARCH, {"sort": "experience"})) == ["Near", "Far"]
    r = api.get(SEARCH, {"sort": "distance", "lat": 23.52, "lng": 87.31})
    assert names(r) == ["Near", "Far"]
    assert r.data["items"][0]["clinic"]["distance_km"] < 1 < r.data["items"][1]["clinic"]["distance_km"]
    assert api.get(SEARCH).data["items"][0]["clinic"]["distance_km"] is None  # no lat/lng: no distance


def test_availability_block_for_a_given_date(api):
    make_doctor(phone="+919810000031")
    r = api.get(SEARCH, {"date": future_day()})
    a = r.data["items"][0]["availability"]
    assert str(a["date"]) == future_day() and a["day_state"] == "open" and a["slots_left"] == 5
    assert len(a["preview_slots"]) == 4 and a["next_available_start"]


def test_day_state_full_and_off(api):
    _, clinic = make_doctor(phone="+919810000041", name="Mon only", weekdays=[1])
    day = timezone.now() + timedelta(days=3)
    monday = day + timedelta(days=(1 - day.astimezone(IST).isoweekday()) % 7 or 7)
    assert api.get(SEARCH, {"date": str(monday.astimezone(IST).date())}).data["items"][0][
        "availability"]["day_state"] == "open"
    # a date filter on an off day excludes the doctor entirely; no filter shows next_available_start
    tuesday = str((monday + timedelta(days=1)).astimezone(IST).date())
    assert api.get(SEARCH, {"date": tuesday}).data["items"] == []
    Slot.objects.filter(clinic=clinic, start_ts__date=monday.date()).update(status="booked")
    assert api.get(SEARCH).data["items"][0]["availability"]["next_available_start"]


def test_doctor_detail_hides_unapproved_and_summarises_schedule(api):
    doc, _ = make_doctor(phone="+919810000051", name="Det", weekdays=[1, 3, 5])
    hidden, _ = make_doctor(phone="+919810000052", approved=False)
    r = api.get(f"{SEARCH}/{doc.pk}")
    assert r.data["doctor"]["verified"] is True and r.data["doctor"]["specialities"][0]["name"] == "Dermatology"
    assert r.data["clinics"][0]["schedule_summary"] == "Mon, Wed, Fri, 4 to 5 pm"
    assert api.get(f"{SEARCH}/{hidden.pk}").status_code == 404


def test_slot_grid_shape_and_off_days(api):
    doc, clinic = make_doctor(phone="+919810000061", weekdays=[1])
    start = future_day(1)
    r = api.get(f"{SEARCH}/{doc.pk}/slots", {"clinic_id": clinic.pk, "from": start, "days": 7})
    assert r.status_code == 200 and len(r.data["days"]) == 7
    open_days = [d for d in r.data["days"] if d["windows"]]
    assert len(open_days) == 1 and open_days[0]["weekday"] == 1
    w = open_days[0]["windows"][0]
    assert (w["start_time"], w["end_time"], w["slot_minutes"]) == ("16:00", "17:00", 12)
    assert [s["seq"] for s in w["slots"]] == [1, 2, 3, 4, 5] and all(s["available"] for s in w["slots"])
    assert not any(s["held_by_me"] or s["overlaps_mine"] for s in w["slots"])


def test_slot_grid_validation_and_clinic_scoping(api):
    doc, clinic = make_doctor(phone="+919810000071")
    other, _ = make_doctor(phone="+919810000072")
    assert api.get(f"{SEARCH}/{doc.pk}/slots").status_code == 400  # clinic_id required
    assert api.get(f"{SEARCH}/{other.pk}/slots", {"clinic_id": clinic.pk}).status_code == 404
    assert len(api.get(f"{SEARCH}/{doc.pk}/slots", {"clinic_id": clinic.pk, "days": 99}).data["days"]) == 14
