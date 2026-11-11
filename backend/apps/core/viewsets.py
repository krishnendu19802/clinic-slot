from rest_framework import mixins, viewsets
from rest_framework.response import Response


class ItemsListMixin(mixins.ListModelMixin):
    """Small bounded lists answer {items: [...]} with no pagination fields (see the API contract)."""

    pagination_class = None

    def list(self, request, *args, **kwargs):
        return Response({"items": self.get_serializer(self.filter_queryset(self.get_queryset()), many=True).data})


class ItemsViewSet(ItemsListMixin, viewsets.GenericViewSet):
    pass
