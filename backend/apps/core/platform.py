"""Tunable business rules. DB row wins; the default lives in code so a fresh DB just works."""
from .models import PlatformSetting

DEFAULTS = {
    "hold_minutes": 8,
    "payment_grace_minutes": 2,
    "booking_cutoff_minutes": 30,
    "free_cancel_hours": 4,
    "late_cancel_refund_percent": 0,
    "horizon_days": 30,
    "max_reschedules": 1,
    "default_slot_minutes": 12,
}


def get(key: str):
    row = PlatformSetting.objects.filter(pk=key).first()
    return row.value if row else DEFAULTS[key]
