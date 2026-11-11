from django.db import models


class Role(models.TextChoices):
    PATIENT = "patient"
    DOCTOR = "doctor"
