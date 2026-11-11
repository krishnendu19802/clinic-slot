"""Auth endpoints as resource viewsets: each one is a single `create` (POST), URLs per the contract."""
from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.exceptions import ApiError

from .serializers import MeUpdateSerializer, OtpRequestSerializer, OtpVerifySerializer, UserSerializer
from .services.account_service import AccountService
from .services.otp_service import OtpService


class OtpThrottle(AnonRateThrottle):
    scope = "otp"


def _set_refresh_cookie(response, token: str) -> None:
    response.set_cookie(settings.REFRESH_COOKIE, token, httponly=True, samesite="Strict",
                        secure=settings.REFRESH_COOKIE_SECURE, path=settings.REFRESH_COOKIE_PATH,
                        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()))


def _require_csrf_header(request) -> None:
    # Cookie-only endpoints: SameSite=Strict plus a custom header a cross-site form cannot send.
    if request.headers.get("X-Requested-With") != "fetch":
        raise ApiError("TOKEN_INVALID", "Missing X-Requested-With header", status_code=401)


class _PublicCreateViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    account = AccountService()
    otp = OtpService()


class OtpRequestViewSet(_PublicCreateViewSet):
    """POST /auth/otp/request"""
    serializer_class = OtpRequestSerializer
    throttle_classes = [OtpThrottle]

    def create(self, request, *args, **kwargs):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        phone, role = data.validated_data["phone"], data.validated_data["role"]
        self.account.assert_role_free(phone=phone, role=role)
        return Response({"retry_after_seconds": self.otp.request(phone=phone)})


class OtpVerifyViewSet(_PublicCreateViewSet):
    """POST /auth/otp/verify"""
    serializer_class = OtpVerifySerializer
    throttle_classes = [OtpThrottle]

    def create(self, request, *args, **kwargs):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        phone, role = data.validated_data["phone"], data.validated_data["role"]
        self.account.assert_role_free(phone=phone, role=role)
        self.otp.verify(phone=phone, code=data.validated_data["otp"])
        user = self.account.get_or_create_user(phone=phone, role=role)
        access, refresh = self.account.issue_tokens(user)
        response = Response({"access": access, "user": UserSerializer(user).data})
        _set_refresh_cookie(response, refresh)
        return response


class RefreshViewSet(_PublicCreateViewSet):
    """POST /auth/refresh (cookie in, rotated cookie out)"""
    serializer_class = TokenRefreshSerializer

    def create(self, request, *args, **kwargs):
        _require_csrf_header(request)
        serializer = self.get_serializer(data={"refresh": request.COOKIES.get(settings.REFRESH_COOKIE, "")})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise ApiError("TOKEN_INVALID", str(e), status_code=401) from e
        response = Response({"access": serializer.validated_data["access"]})
        _set_refresh_cookie(response, serializer.validated_data["refresh"])
        return response


class LogoutViewSet(_PublicCreateViewSet):
    """POST /auth/logout"""
    serializer_class = None

    def create(self, request, *args, **kwargs):
        _require_csrf_header(request)
        token = request.COOKIES.get(settings.REFRESH_COOKIE)
        if token:
            try:
                RefreshToken(token).blacklist()
            except TokenError:
                pass  # already invalid: nothing to revoke
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(settings.REFRESH_COOKIE, path=settings.REFRESH_COOKIE_PATH)
        return response


class MeViewSet(viewsets.GenericViewSet):
    """GET/PATCH /me. Mapped with as_view in config.api, so there is no pk in the URL."""
    serializer_class = UserSerializer
    account = AccountService()

    def retrieve(self, request):
        return Response(UserSerializer(request.user).data)

    def partial_update(self, request):
        data = MeUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = self.account.update_me(
            user=request.user, name=v.get("name"), email=v.get("email"), email_given="email" in v)
        return Response(UserSerializer(user).data)
