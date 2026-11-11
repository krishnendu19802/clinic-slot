from rest_framework import mixins, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.core.exceptions import ApiError
from apps.core.permissions import IsDoctor
from apps.core.viewsets import ItemsListMixin, ItemsViewSet

from .repo.psql.reference_repo import ReferenceRepo
from .serializers import CouncilSerializer, DoctorProfileSerializer, DocumentSerializer, SpecialitySerializer
from .services.document_service import DocumentService
from .services.profile_service import ProfileService

_refs = ReferenceRepo()


class CouncilViewSet(ItemsViewSet):
    """GET /councils"""
    permission_classes = []
    authentication_classes: list = []
    serializer_class = CouncilSerializer
    queryset = _refs.councils()


class SpecialityViewSet(ItemsViewSet):
    """GET /specialities"""
    permission_classes = []
    authentication_classes: list = []
    serializer_class = SpecialitySerializer
    queryset = _refs.specialities()


class DoctorProfileViewSet(viewsets.GenericViewSet):
    """GET/PATCH /doctor/profile (mapped with as_view, no pk)."""
    permission_classes = [IsDoctor]
    serializer_class = DoctorProfileSerializer
    service = ProfileService()

    def retrieve(self, request):
        return Response(self.get_serializer(self.service.get(user=request.user)).data)

    def partial_update(self, request):
        data = self.get_serializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        fields = dict(data.validated_data)
        specialities = fields.pop("specialities", None)
        profile = self.service.update(user=request.user, fields=fields, specialities=specialities)
        return Response(self.get_serializer(profile).data)


class DoctorSubmissionViewSet(viewsets.GenericViewSet):
    """POST /doctor/profile/submit: submitting is creating a submission."""
    permission_classes = [IsDoctor]
    serializer_class = DoctorProfileSerializer
    service = ProfileService()

    def create(self, request):
        return Response(self.get_serializer(self.service.submit(user=request.user)).data)


class DoctorDocumentViewSet(ItemsListMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin,
                            viewsets.GenericViewSet):
    """GET/POST /doctor/documents, DELETE /doctor/documents/{id}"""
    permission_classes = [IsDoctor]
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]
    service = DocumentService()

    def get_queryset(self):
        return self.service.list(user=self.request.user)

    def create(self, request, *args, **kwargs):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        document = self.service.upload(user=request.user, doc_type=data.validated_data["type"],
                                       file=data.validated_data["file"])
        return Response(self.get_serializer(document).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        if not self.service.delete(user=request.user, document_id=int(kwargs["pk"])):
            raise ApiError("NOT_FOUND", "Document not found", status_code=404)
        return Response(status=status.HTTP_204_NO_CONTENT)
