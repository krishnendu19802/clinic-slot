from celery import shared_task


@shared_task
def reconcile():
    """Nightly: match Razorpay payments to bookings. Implemented with the payments service."""
