"""All OTP-related Redis keys live here; the service never touches the cache directly."""
from django.core.cache import cache


class OtpRepo:
    def acquire_cooldown(self, phone: str, seconds: int) -> bool:
        return cache.add(f"otp_cd:{phone}", 1, seconds)

    def count_send(self, phone: str) -> int:
        cache.add(f"otp_sends:{phone}", 0, 3600)
        return cache.incr(f"otp_sends:{phone}")

    def store(self, phone: str, code_hash: str, ttl: int) -> None:
        cache.set(f"otp:{phone}", code_hash, ttl)
        cache.set(f"otp_att:{phone}", 0, ttl)

    def get_hash(self, phone: str) -> str | None:
        return cache.get(f"otp:{phone}")

    def attempts(self, phone: str) -> int:
        return cache.get(f"otp_att:{phone}", 0)

    def add_attempt(self, phone: str) -> None:
        cache.incr(f"otp_att:{phone}")

    def clear(self, phone: str) -> None:
        cache.delete_many([f"otp:{phone}", f"otp_att:{phone}"])
