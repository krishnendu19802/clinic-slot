"""Pure booking rules (no DB): cancellation / reschedule eligibility."""
from datetime import datetime, timedelta

from apps.core import platform

from .enums import BookingStatus


def reschedule_block(*, booking, now: datetime) -> str | None:
    """Reason code why a patient cannot reschedule, or None if they can."""
    if booking.status != BookingStatus.CONFIRMED or booking.slot.start_ts <= now:
        return "not_confirmed"
    if booking.slot.start_ts - now < timedelta(hours=platform.get("free_cancel_hours")):
        return "within_free_cancel_window"
    if booking.reschedule_count >= platform.get("max_reschedules"):
        return "max_reschedules"
    return None
