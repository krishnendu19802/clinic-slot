from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.enums import Role
from apps.accounts.models import User
from apps.accounts.repo.psql.patient_profile_repo import PatientProfileRepo
from apps.accounts.repo.psql.user_repo import UserRepo
from apps.core.exceptions import ApiError
from apps.doctors.repo.psql.doctor_profile_repo import DoctorProfileRepo


class AccountService:
    def __init__(self, users=None, patients=None, doctors=None):
        self.users = users or UserRepo()
        self.patients = patients or PatientProfileRepo()
        self.doctors = doctors or DoctorProfileRepo()

    def assert_role_free(self, phone: str, role: str) -> None:
        """One phone, one role: an existing account of the other role blocks the login."""
        user = self.users.get_by_phone(phone)
        if user and user.role != role:
            raise ApiError("ROLE_MISMATCH", f"This number is registered as a {user.role}")
        if user and not user.is_active:
            raise ApiError("ACCOUNT_DISABLED", "Account disabled", status_code=403)

    @transaction.atomic
    def get_or_create_user(self, phone: str, role: str) -> User:
        self.assert_role_free(phone, role)
        user = self.users.get_by_phone(phone)
        if user:
            return user
        user = self.users.create(phone, role)
        (self.patients if role == Role.PATIENT else self.doctors).create_blank(user)
        return user

    @staticmethod
    def issue_tokens(user: User) -> tuple[str, str]:
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token), str(refresh)

    def update_me(self, user: User, name: str | None, email: str | None, email_given: bool) -> User:
        if email_given:
            self.users.set_email(user, email)
        if name is not None:
            if user.role == Role.PATIENT:
                self.patients.set_name(user.patient_profile, name)
            else:
                self.doctors.set_name(user.doctor_profile, name)
        return user
