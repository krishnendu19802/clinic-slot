from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q

from .enums import Role


class UserManager(BaseUserManager):
    def create_user(self, phone: str, role: str):
        user = self.model(phone=phone, role=role)
        user.set_unusable_password()  # patients/doctors only ever log in by OTP
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str):
        user = self.model(email=self.normalize_email(email), is_staff=True, is_superuser=True)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """Admin is not a role: staff have email+password, no phone, and never get a JWT."""

    phone = models.CharField(max_length=16, unique=True, null=True, blank=True)  # E.164
    email = models.EmailField(unique=True, null=True, blank=True)
    role = models.CharField(max_length=8, choices=Role.choices, null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    objects = UserManager()

    class Meta:
        constraints = [models.CheckConstraint(
            condition=Q(is_staff=True) | (Q(phone__isnull=False) & Q(role__isnull=False)),
            name="user_phone_and_role_unless_staff",
        )]

    @property
    def display_name(self) -> str:
        profile = getattr(self, "patient_profile", None) or getattr(self, "doctor_profile", None)
        return profile.full_name if profile else ""


class PatientProfile(models.Model):
    user = models.OneToOneField(User, primary_key=True, related_name="patient_profile", on_delete=models.CASCADE)
    full_name = models.CharField(max_length=120, blank=True)
