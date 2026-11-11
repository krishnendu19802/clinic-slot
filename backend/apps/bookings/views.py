from rest_framework import mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.core.permissions import IsPatient
from apps.core.viewsets import ItemsListMixin

from .serializers import BookingCreateSerializer, BookingDetailsInSerializer, BookingSerializer
from .services.booking_service import BookingService


class BookingViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """POST /bookings (place a hold), GET /bookings?tab=, GET /bookings/{id}, PATCH /bookings/{id} (details)."""
    permission_classes = [IsPatient]
    serializer_class = BookingSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "booking"
    http_method_names = ["get", "post", "patch", "head", "options"]
    service = BookingService()

    def get_queryset(self):
        return self.service.list(user=self.request.user, tab=self.request.query_params.get("tab", "upcoming"))

    def retrieve(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.service.get(user=request.user, booking_id=int(kwargs["pk"]))).data)

    def create(self, request, *args, **kwargs):
        data = BookingCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        booking, created = self.service.place_hold(user=request.user, slot_id=data.validated_data["slot_id"])
        return Response(self.get_serializer(booking).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        data = BookingDetailsInSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        booking = self.service.update_details(user=request.user, booking_id=int(kwargs["pk"]),
                                              patient=data.validated_data["patient"])
        return Response(self.get_serializer(booking).data)


class ActiveHoldViewSet(ItemsListMixin, viewsets.GenericViewSet):
    """GET /bookings/active-holds: live holds, soonest-expiring first (resume after a reload)."""
    permission_classes = [IsPatient]
    serializer_class = BookingSerializer
    service = BookingService()

    def get_queryset(self):
        return self.service.holds(user=self.request.user)


class BookingReleaseViewSet(viewsets.GenericViewSet):
    """POST /bookings/{booking_id}/release"""
    permission_classes = [IsPatient]
    serializer_class = None
    service = BookingService()

    def create(self, request, booking_id: int):
        self.service.release(user=request.user, booking_id=booking_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
