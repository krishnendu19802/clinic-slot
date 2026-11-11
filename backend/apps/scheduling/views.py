from datetime import date

from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.exceptions import ApiError
from apps.core.permissions import IsDoctor
from apps.core.viewsets import ItemsListMixin

from .serializers import (
    ClinicSerializer,
    DoctorSlotSerializer,
    ExceptionSerializer,
    ScheduleInSerializer,
    WindowOutSerializer,
)
from .services.availability_service import AvailabilityService
from .services.clinic_service import ClinicService
from .services.schedule_service import ScheduleService
from .services.slot_generation_service import GenerationResult
from .services.slot_service import SlotService


def _result(result: GenerationResult) -> dict:
    return {"slots_generated": result.generated, "conflicts": result.conflicts}


class ClinicViewSet(ItemsListMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin,
                    viewsets.GenericViewSet):
    """GET/POST /doctor/clinics, PUT/PATCH/DELETE /doctor/clinics/{id}"""
    permission_classes = [IsDoctor]
    serializer_class = ClinicSerializer
    service = ClinicService()

    def get_queryset(self):
        return self.service.list(user=self.request.user)

    def create(self, request, *args, **kwargs):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        clinic = self.service.create(user=request.user, fields=dict(data.validated_data))
        return Response(self.get_serializer(clinic).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        data = self.get_serializer(data=request.data, partial=kwargs.get("partial", False))
        data.is_valid(raise_exception=True)
        clinic = self.service.update(user=request.user, clinic_id=int(kwargs["pk"]), fields=dict(data.validated_data))
        return Response(self.get_serializer(clinic).data)

    def destroy(self, request, *args, **kwargs):
        self.service.delete(user=request.user, clinic_id=int(kwargs["pk"]))
        return Response(status=status.HTTP_204_NO_CONTENT)


class ScheduleViewSet(viewsets.GenericViewSet):
    """GET/PUT /doctor/clinics/{clinic_id}/schedule (mapped with as_view)."""
    permission_classes = [IsDoctor]
    serializer_class = ScheduleInSerializer
    service = ScheduleService()

    def retrieve(self, request, clinic_id: int):
        data = self.service.get(user=request.user, clinic_id=clinic_id)
        return Response({"windows": WindowOutSerializer(data["windows"], many=True).data,
                         "exceptions": ExceptionSerializer(data["exceptions"], many=True).data})

    def update(self, request, clinic_id: int):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = self.service.replace(user=request.user, clinic_id=clinic_id,
                                      windows=data.validated_data["windows"])
        return Response(_result(result))


class ExceptionViewSet(viewsets.GenericViewSet):
    """POST /doctor/clinics/{clinic_id}/exceptions, DELETE .../exceptions/{pk}"""
    permission_classes = [IsDoctor]
    serializer_class = ExceptionSerializer
    service = ScheduleService()

    def create(self, request, clinic_id: int):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = self.service.add_exception(user=request.user, clinic_id=clinic_id, fields=dict(data.validated_data))
        return Response(_result(result), status=status.HTTP_201_CREATED)

    def destroy(self, request, clinic_id: int, pk: int):
        return Response(_result(self.service.remove_exception(user=request.user, clinic_id=clinic_id,
                                                              exception_id=pk)))


class DoctorSlotViewSet(viewsets.GenericViewSet):
    """GET /doctor/clinics/{clinic_id}/slots?date=YYYY-MM-DD: the owner's view in any status."""
    permission_classes = [IsDoctor]
    serializer_class = DoctorSlotSerializer
    service = SlotService()

    def list(self, request, clinic_id: int):
        try:
            day = date.fromisoformat(request.query_params.get("date", date.today().isoformat()))
        except ValueError as e:
            raise ApiError("VALIDATION_ERROR", "date must be YYYY-MM-DD", status_code=400) from e
        slots = self.service.day(user=request.user, clinic_id=clinic_id, date=day)
        return Response({"items": self.get_serializer(slots, many=True).data})


class SlotBlockViewSet(viewsets.GenericViewSet):
    """POST /doctor/slots/{slot_id}/block blocks a slot; DELETE on the same resource unblocks it."""
    permission_classes = [IsDoctor]
    serializer_class = DoctorSlotSerializer
    service = SlotService()

    def create(self, request, slot_id: int):
        slot = self.service.block(user=request.user, slot_id=slot_id)
        return Response(self.get_serializer(slot).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, slot_id: int):
        self.service.unblock(user=request.user, slot_id=slot_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicSlotGridViewSet(viewsets.GenericViewSet):
    """GET /doctors/{doctor_id}/slots?clinic_id=&from=&days=. Public; a Bearer token (optional) personalises it."""
    permission_classes = [AllowAny]
    serializer_class = None
    service = AvailabilityService()

    def list(self, request, doctor_id: int):
        q = request.query_params
        try:
            start = date.fromisoformat(q["from"]) if "from" in q else date.today()
            clinic_id, days = int(q["clinic_id"]), int(q.get("days", 7))
        except (KeyError, ValueError) as e:
            raise ApiError("VALIDATION_ERROR", "clinic_id (int), from (YYYY-MM-DD) and days (int) are required/valid",
                           status_code=400) from e
        return Response(self.service.grid(doctor_id=doctor_id, clinic_id=clinic_id, start_date=start, days=days,
                                          viewer=request.user))
