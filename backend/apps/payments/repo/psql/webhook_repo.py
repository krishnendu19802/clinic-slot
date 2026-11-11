from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.payments.models import ReconciliationIssue, WebhookEvent


class WebhookRepo:
    def create_if_new(self, *, event_id: str, type: str, payload: dict) -> WebhookEvent | None:
        """Insert-first idempotency: None means this event id was already received."""
        try:
            with transaction.atomic():
                return WebhookEvent.objects.create(razorpay_event_id=event_id, type=type, payload=payload)
        except IntegrityError:
            return None

    def finish(self, *, event: WebhookEvent, error: str = "") -> None:
        event.processed_at, event.error = timezone.now(), error
        event.save(update_fields=["processed_at", "error"])

    def add_issue(self, *, kind: str, booking, payment, detail: str) -> None:
        ReconciliationIssue.objects.create(kind=kind, booking=booking, payment=payment, detail=detail)
