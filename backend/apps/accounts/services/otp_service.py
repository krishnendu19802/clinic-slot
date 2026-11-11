"""OTP lifecycle: HMAC-hashed code + TTL, attempt cap, resend cooldown, hourly send cap."""
import hashlib
import hmac
import secrets

from django.conf import settings
from rest_framework.exceptions import Throttled

from apps.accounts.repo.redis.otp_repo import OtpRepo
from apps.core.exceptions import ApiError
from apps.notifications.sms import send_sms

DEV_CODE = "123456"


class OtpService:
    def __init__(self, repo: OtpRepo | None = None, sms=send_sms):
        self.repo = repo or OtpRepo()
        self.sms = sms

    @staticmethod
    def _hash(*, phone: str, code: str) -> str:
        return hmac.new(settings.SECRET_KEY.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()

    def request(self, *, phone: str) -> int:
        """Send an OTP; returns the resend cooldown in seconds."""
        cooldown = settings.OTP_RESEND_SECONDS
        if not self.repo.acquire_cooldown(phone=phone, seconds=cooldown):
            raise Throttled(wait=cooldown)
        if self.repo.count_send(phone=phone) > settings.OTP_MAX_SENDS_PER_HOUR:
            raise Throttled(wait=3600)
        code = DEV_CODE if settings.OTP_DEV_FIXED else f"{secrets.randbelow(10**6):06d}"
        code_hash = self._hash(phone=phone, code=code)
        self.repo.store(phone=phone, code_hash=code_hash, ttl=settings.OTP_TTL_SECONDS)
        self.sms(phone=phone, text=f"Your ClinicSlot OTP is {code}. It expires in 5 minutes.")
        return cooldown

    def verify(self, *, phone: str, code: str) -> None:
        stored = self.repo.get_hash(phone=phone)
        if stored is None:
            raise ApiError("OTP_EXPIRED", "OTP expired, request a new one", status_code=400)
        if self.repo.attempts(phone=phone) >= settings.OTP_MAX_ATTEMPTS:
            raise ApiError("OTP_LOCKED", "Too many attempts", status_code=429)
        if not hmac.compare_digest(stored, self._hash(phone=phone, code=code)):
            self.repo.add_attempt(phone=phone)
            raise ApiError("OTP_INVALID", "Incorrect OTP", status_code=400)
        self.repo.clear(phone=phone)
