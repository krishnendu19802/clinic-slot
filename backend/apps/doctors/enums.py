from django.db import models


class Gender(models.TextChoices):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Verification(models.TextChoices):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    INFO_REQUESTED = "info_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class RegistryCheck(models.TextChoices):
    PASSED = "passed"
    FAILED = "failed"


class DocType(models.TextChoices):
    REGISTRATION = "registration"
    DEGREE = "degree"
    ID = "id"
