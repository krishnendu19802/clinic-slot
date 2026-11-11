from celery import shared_task


@shared_task
def generate_slots():
    """Nightly: extend the rolling horizon. Implemented with the scheduling service."""
