from celery import shared_task
from django.db import transaction

from apps.scheduling.repo.psql.clinic_repo import ClinicRepo
from apps.scheduling.services.slot_generation_service import SlotGenerationService


@shared_task
def generate_slots() -> int:
    """Nightly: extend every approved clinic's rolling horizon. One transaction + lock per clinic."""
    clinics, generator, total = ClinicRepo(), SlotGenerationService(), 0
    for clinic in clinics.approved_active():
        with transaction.atomic():
            total += generator.generate(clinic=clinics.lock(clinic=clinic)).generated
    return total
