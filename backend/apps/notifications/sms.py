import logging

from django.conf import settings

log = logging.getLogger(__name__)


def send_sms(phone: str, text: str) -> None:
    """Sync send. `console` backend just logs; a real provider plugs in here (short timeout)."""
    if settings.SMS_BACKEND == "console":
        log.warning("SMS to %s: %s", phone, text)
        return
    raise NotImplementedError(settings.SMS_BACKEND)
