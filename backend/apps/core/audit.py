from .models import AuditLog


def log(*, actor, action: str, entity, **data) -> None:
    AuditLog.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        entity_type=entity._meta.model_name,
        entity_id=entity.pk,
        data=data,
    )
