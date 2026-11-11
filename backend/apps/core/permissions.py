from rest_framework.permissions import BasePermission


class _Role(BasePermission):
    role = ""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == self.role)


class IsPatient(_Role):
    role = "patient"


class IsDoctor(_Role):
    role = "doctor"
