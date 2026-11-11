from django.conf import settings
from django.db import models


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PlatformSetting(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    value = models.JSONField()


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=32)
    entity_id = models.BigIntegerField()
    data = models.JSONField(default=dict, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["entity_type", "entity_id"])]
