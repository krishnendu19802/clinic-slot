import hashlib
import json

from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.bookings.serializers import BookingSerializer
from apps.core.exceptions import ApiError
from apps.core.permissions import IsPatient

from .serializers import PaymentVerifyInSerializer
from .services.payment_service import PaymentService


class BookingPayViewSet(viewsets.GenericViewSet):
    """POST /bookings/{booking_id}/pay: creating a payment order (idempotent per hold)."""
    permission_classes = [IsPatient]
    serializer_class = None
    service = PaymentService()

    def create(self, request, booking_id: int):
        return Response(self.service.create_order(user=request.user, booking_id=booking_id))


class PaymentVerifyViewSet(viewsets.GenericViewSet):
    """POST /bookings/{booking_id}/payment/verify"""
    permission_classes = [IsPatient]
    serializer_class = PaymentVerifyInSerializer
    service = PaymentService()

    def create(self, request, booking_id: int):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        booking = self.service.verify(user=request.user, booking_id=booking_id, **data.validated_data)
        return Response(BookingSerializer(booking).data)


class RazorpayWebhookViewSet(viewsets.GenericViewSet):
    """POST /webhooks/razorpay: no JWT, authenticated by the signature header. 200 once the event is stored."""
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = None
    service = PaymentService()

    def create(self, request):
        body = request.body  # raw bytes: read before DRF parses anything
        try:
            payload = json.loads(body)
        except ValueError as e:
            raise ApiError("VALIDATION_ERROR", "Body is not JSON", status_code=400) from e
        event_id = request.headers.get("X-Razorpay-Event-Id") or hashlib.sha256(body).hexdigest()
        self.service.handle_webhook(body=body, signature=request.headers.get("X-Razorpay-Signature", ""),
                                    event_id=event_id, payload=payload)
        return Response(status=status.HTTP_200_OK)
