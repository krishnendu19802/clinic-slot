from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class Pagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({"items": data, "page": self.page.number,
                         "page_size": self.page.paginator.per_page, "total": self.page.paginator.count})
