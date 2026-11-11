from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import TimeStamped

from .enums import DocType, Gender, RegistryCheck, Verification


class Council(models.Model):
    name = models.CharField(max_length=120, unique=True)


class Speciality(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    blurb = models.CharField(max_length=160, blank=True)

    class Meta:
        verbose_name_plural = "specialities"


class DoctorProfile(TimeStamped):
    # Everything is optional while in `draft`; completeness is enforced at submit.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, primary_key=True, related_name="doctor_profile",
                                on_delete=models.CASCADE)
    full_name = models.CharField(max_length=120, blank=True)
    gender = models.CharField(max_length=8, choices=Gender.choices, blank=True)
    registration_no = models.CharField(max_length=40, blank=True)
    council = models.ForeignKey(Council, null=True, blank=True, on_delete=models.PROTECT)
    degrees = ArrayField(models.CharField(max_length=40), default=list, blank=True)
    specialities = models.ManyToManyField(Speciality, blank=True, related_name="doctors")
    experience_years = models.PositiveSmallIntegerField(null=True, blank=True)
    fee_paise = models.PositiveIntegerField(null=True, blank=True)
    languages = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    remarks = models.TextField(blank=True)
    verification_status = models.CharField(max_length=16, choices=Verification.choices, default=Verification.DRAFT)
    registry_check = models.CharField(max_length=8, choices=RegistryCheck.choices, null=True, blank=True)
    status_reason = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["council", "registration_no"], condition=~models.Q(registration_no=""),
            name="uniq_council_registration")]

    @property
    def id(self) -> int:
        return self.user_id


class DoctorDocument(models.Model):
    doctor = models.ForeignKey(DoctorProfile, related_name="documents", on_delete=models.CASCADE)
    type = models.CharField(max_length=14, choices=DocType.choices)
    file = models.FileField(upload_to="doctor_docs/")  # private MEDIA_ROOT, served only via authed views
    original_name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=80)
    size_bytes = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["doctor", "type"], name="one_document_per_type")]
