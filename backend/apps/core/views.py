from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import platform


class PolicyViewSet(viewsets.GenericViewSet):
    """GET /policy: the numbers and the sentence shown before payment and on confirmation."""
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = None

    def list(self, request):
        free_hours, late = platform.get("free_cancel_hours"), platform.get("late_cancel_refund_percent")
        late_text = "no refund" if late == 0 else f"a {late}% refund"
        return Response({
            "hold_minutes": platform.get("hold_minutes"),
            "cutoff_minutes": platform.get("booking_cutoff_minutes"),
            "free_cancel_hours": free_hours,
            "late_cancel_refund_percent": late,
            "default_slot_minutes": platform.get("default_slot_minutes"),
            "text": (f"Cancel at least {free_hours} hours before your slot for a full refund. "
                     f"Inside {free_hours} hours: {late_text}. If the doctor cancels, you always get a full refund."),
        })
