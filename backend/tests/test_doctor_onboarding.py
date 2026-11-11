import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.doctors import views as doctor_views
from apps.doctors.models import Council, DoctorDocument, Speciality

from .helpers import login

pytestmark = pytest.mark.django_db
URL = "/api/v1/doctor"


@pytest.fixture
def doc():
    return login("doctor", "+919800022222")


def pdf(name="x.pdf", size=100, ctype="application/pdf"):
    return SimpleUploadedFile(name, b"%PDF" + b"0" * size, content_type=ctype)


def fill_profile(api):
    return api.patch(f"{URL}/profile", {
        "full_name": "Dr A Sen", "gender": "male", "registration_no": "WBMC-1", "degrees": ["MBBS", "MD"],
        "council_id": Council.objects.first().pk, "specialities": [Speciality.objects.first().pk],
        "experience_years": 12, "fee_paise": 50000, "languages": ["English", "Bengali"],
    }, format="json")


def upload_all(api):
    for t in ("registration", "degree", "id"):
        assert api.post(f"{URL}/documents", {"type": t, "file": pdf()}, format="multipart").status_code == 201


def test_seeded_reference_lists_are_public():
    from rest_framework.test import APIClient
    api = APIClient()
    assert len(api.get("/api/v1/specialities").data["items"]) >= 5
    assert len(api.get("/api/v1/councils").data["items"]) >= 1


def test_patient_cannot_use_doctor_endpoints():
    r = login("patient", "+919800033333").get(f"{URL}/profile")
    assert r.status_code == 403 and r.data["error"]["code"] == "ROLE_FORBIDDEN"


def test_partial_save_draft_and_validation(doc):
    r = doc.patch(f"{URL}/profile", {"full_name": "Dr A Sen"}, format="json")
    assert r.status_code == 200 and r.data["verification_status"] == "draft"
    bad = doc.patch(f"{URL}/profile", {"languages": ["Klingon"]}, format="json")
    assert bad.status_code == 400 and bad.data["error"]["code"] == "VALIDATION_ERROR"
    assert fill_profile(doc).data["specialities"]


def test_duplicate_registration_number_is_rejected(doc):
    fill_profile(doc)
    other = login("doctor", "+919800055555")
    r = fill_profile(other)
    assert r.status_code == 400 and "registration_no" in r.data["error"]["fields"]


def test_submit_lists_everything_missing(doc):
    r = doc.post(f"{URL}/profile/submit")
    assert r.status_code == 400
    fields = r.data["error"]["fields"]
    assert {"full_name", "registration_no", "specialities", "document_registration", "document_id"} <= set(fields)


@pytest.mark.parametrize(("roll", "expected"), [(0.1, "passed"), (0.95, "failed")])
def test_submit_runs_simulated_registry_then_locks_profile(doc, monkeypatch, roll, expected):
    monkeypatch.setattr(doctor_views.DoctorSubmissionViewSet.service.registry, "rng", lambda: roll)
    fill_profile(doc)
    upload_all(doc)
    r = doc.post(f"{URL}/profile/submit")
    assert r.status_code == 200
    assert r.data["verification_status"] == "submitted" and r.data["registry_check"] == expected
    locked = doc.patch(f"{URL}/profile", {"remarks": "x"}, format="json")
    assert locked.status_code == 409 and locked.data["error"]["code"] == "PROFILE_LOCKED"
    assert doc.post(f"{URL}/documents", {"type": "id", "file": pdf()}, format="multipart").status_code == 409


def test_document_rules_and_one_per_type(doc):
    big = doc.post(f"{URL}/documents", {"type": "id", "file": pdf(size=6 * 1024 * 1024)}, format="multipart")
    assert big.status_code == 400
    wrong = doc.post(f"{URL}/documents", {"type": "id", "file": pdf("x.exe", ctype="application/x-msdownload")},
                     format="multipart")
    assert wrong.status_code == 400
    doc.post(f"{URL}/documents", {"type": "id", "file": pdf()}, format="multipart")
    second = doc.post(f"{URL}/documents", {"type": "id", "file": pdf("new.pdf")}, format="multipart")
    assert DoctorDocument.objects.count() == 1 and second.data["name"] == "new.pdf"
    assert "file" not in second.data  # never leak a storage path


def test_cannot_delete_another_doctors_document(doc):
    mine = doc.post(f"{URL}/documents", {"type": "id", "file": pdf()}, format="multipart").data["id"]
    other = login("doctor", "+919800044444")
    assert other.delete(f"{URL}/documents/{mine}").status_code == 404
    assert doc.delete(f"{URL}/documents/{mine}").status_code == 204
