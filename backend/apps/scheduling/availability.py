"""The one definition of 'a slot a patient can book right now' (lazy hold expiry included)."""
from datetime import datetime

from django.db.models import Q

from .enums import SlotStatus


def open_q(*, prefix: str, now: datetime, earliest: datetime) -> Q:
    """Q for querysets: `prefix` is '' on Slot, 'slots__' from Clinic."""
    free = Q(**{f"{prefix}status": SlotStatus.AVAILABLE}) | Q(
        **{f"{prefix}status": SlotStatus.HELD, f"{prefix}held_until__lt": now})
    return free & Q(**{f"{prefix}start_ts__gt": earliest})


def is_open(*, slot, now: datetime, earliest: datetime) -> bool:
    free = slot.status == SlotStatus.AVAILABLE or (
        slot.status == SlotStatus.HELD and slot.held_until is not None and slot.held_until < now)
    return free and slot.start_ts > earliest
