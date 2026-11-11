"""One router for the whole /api/v1 surface; each app registers its viewsets here."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import LogoutViewSet, MeViewSet, OtpRequestViewSet, OtpVerifyViewSet, RefreshViewSet
from apps.doctors.views import (
    CouncilViewSet,
    DoctorDocumentViewSet,
    DoctorProfileViewSet,
    DoctorSubmissionViewSet,
    SpecialityViewSet,
)
from apps.scheduling.views import (
    ClinicViewSet,
    DoctorSlotViewSet,
    ExceptionViewSet,
    ScheduleViewSet,
    SlotBlockViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register("auth/otp/request", OtpRequestViewSet, basename="otp-request")
router.register("auth/otp/verify", OtpVerifyViewSet, basename="otp-verify")
router.register("auth/refresh", RefreshViewSet, basename="auth-refresh")
router.register("auth/logout", LogoutViewSet, basename="auth-logout")

router.register("councils", CouncilViewSet, basename="council")
router.register("specialities", SpecialityViewSet, basename="speciality")
router.register("doctor/profile/submit", DoctorSubmissionViewSet, basename="doctor-submit")
router.register("doctor/clinics", ClinicViewSet, basename="doctor-clinic")
router.register("doctor/documents", DoctorDocumentViewSet, basename="doctor-document")

urlpatterns = [
    path("doctor/clinics/<int:clinic_id>/schedule", ScheduleViewSet.as_view({"get": "retrieve", "put": "update"})),
    path("doctor/clinics/<int:clinic_id>/exceptions", ExceptionViewSet.as_view({"post": "create"})),
    path("doctor/clinics/<int:clinic_id>/exceptions/<int:pk>", ExceptionViewSet.as_view({"delete": "destroy"})),
    path("doctor/clinics/<int:clinic_id>/slots", DoctorSlotViewSet.as_view({"get": "list"})),
    path("doctor/slots/<int:slot_id>/block", SlotBlockViewSet.as_view({"post": "create", "delete": "destroy"})),
    path("doctor/profile", DoctorProfileViewSet.as_view({"get": "retrieve", "patch": "partial_update"})),
    path("me", MeViewSet.as_view({"get": "retrieve", "patch": "partial_update"})),
    *router.urls,
]
