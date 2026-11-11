from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .public_serializers import SearchParamsSerializer
from .services.search_service import SearchService


class PublicDoctorViewSet(viewsets.GenericViewSet):
    """GET /doctors (search) and GET /doctors/{id} (profile). Public; only approved doctors are visible."""
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = SearchParamsSerializer
    service = SearchService()

    def list(self, request):
        params = self.get_serializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        filters = dict(params.validated_data)
        sort = filters.pop("sort")
        page = self.paginate_queryset(self.service.queryset(filters=filters, sort=sort))
        return self.get_paginated_response(self.service.results(clinics=page, day=filters.get("date")))

    def retrieve(self, request, pk=None):
        return Response(self.service.detail(doctor_id=int(pk)))
