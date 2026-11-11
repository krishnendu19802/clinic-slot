import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PatientProfile
from apps.doctors.models import DoctorProfile

pytestmark = pytest.mark.django_db
PHONE = "+919800011111"
H = {"HTTP_X_REQUESTED_WITH": "fetch"}


@pytest.fixture
def api():
    return APIClient()


def login(api, role="patient", phone=PHONE):
    assert api.post("/api/v1/auth/otp/request", {"phone": phone, "role": role}, format="json").status_code == 200
    return api.post("/api/v1/auth/otp/verify", {"phone": phone, "role": role, "otp": "123456"}, format="json")


def test_patient_login_creates_user_profile_and_refresh_cookie(api):
    r = login(api)
    assert r.status_code == 200
    assert r.data["user"]["role"] == "patient" and r.data["user"]["doctor"] is None
    assert PatientProfile.objects.count() == 1
    cookie = r.cookies["refresh"]
    assert cookie["httponly"] and cookie["samesite"] == "Strict" and cookie["path"] == "/api/v1/auth"


def test_doctor_login_always_has_a_draft_doctor_object(api):
    r = login(api, "doctor")
    assert r.data["user"]["doctor"]["verification_status"] == "draft"
    assert DoctorProfile.objects.count() == 1


def test_phone_is_normalised_to_e164(api):
    r = login(api, phone="98000 11111")
    assert r.data["user"]["phone"] == PHONE


def test_other_role_on_same_phone_is_rejected_with_error_envelope(api):
    login(api, "patient")
    api.cookies.clear()
    r = api.post("/api/v1/auth/otp/request", {"phone": PHONE, "role": "doctor"}, format="json")
    assert r.status_code == 409 and r.data["error"]["code"] == "ROLE_MISMATCH"


def test_wrong_otp_and_resend_cooldown(api):
    api.post("/api/v1/auth/otp/request", {"phone": PHONE, "role": "patient"}, format="json")
    bad = api.post("/api/v1/auth/otp/verify", {"phone": PHONE, "role": "patient", "otp": "000000"}, format="json")
    assert bad.status_code == 400 and bad.data["error"]["code"] == "OTP_INVALID"
    again = api.post("/api/v1/auth/otp/request", {"phone": PHONE, "role": "patient"}, format="json")
    assert again.status_code == 429 and again.data["error"]["details"]["retry_after_seconds"] == 30


def test_me_requires_a_token_and_patch_updates_name(api):
    r = api.get("/api/v1/me")
    assert r.status_code == 401 and r.data["error"]["code"] == "TOKEN_INVALID"
    access = login(api).data["access"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    r = api.patch("/api/v1/me", {"name": "Asha", "email": "a@example.com"}, format="json")
    assert r.status_code == 200 and r.data["name"] == "Asha" and r.data["profile_complete"] is True
    assert api.get("/api/v1/me").data["email"] == "a@example.com"


def test_refresh_needs_csrf_header_rotates_and_logout_blacklists(api):
    login(api)
    assert api.post("/api/v1/auth/refresh").status_code == 401  # no X-Requested-With
    old = api.cookies["refresh"].value
    r = api.post("/api/v1/auth/refresh", **H)
    assert r.status_code == 200 and "access" in r.data
    assert r.cookies["refresh"].value != old  # rotated
    api.cookies["refresh"] = old  # replaying the rotated-out token must fail
    assert api.post("/api/v1/auth/refresh", **H).status_code == 401
    api.cookies["refresh"] = r.cookies["refresh"].value
    assert api.post("/api/v1/auth/logout", **H).status_code == 204
    api.cookies["refresh"] = r.cookies["refresh"].value
    assert api.post("/api/v1/auth/refresh", **H).status_code == 401
