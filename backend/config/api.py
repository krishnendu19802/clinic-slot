"""One router for the whole /api/v1 surface; each app registers its viewsets here."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import LogoutViewSet, MeViewSet, OtpRequestViewSet, OtpVerifyViewSet, RefreshViewSet

router = DefaultRouter(trailing_slash=False)
router.register("auth/otp/request", OtpRequestViewSet, basename="otp-request")
router.register("auth/otp/verify", OtpVerifyViewSet, basename="otp-verify")
router.register("auth/refresh", RefreshViewSet, basename="auth-refresh")
router.register("auth/logout", LogoutViewSet, basename="auth-logout")

urlpatterns = [
    path("me", MeViewSet.as_view({"get": "retrieve", "patch": "partial_update"})),
    *router.urls,
]
