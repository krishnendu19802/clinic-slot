from celery import shared_task


@shared_task
def tick() -> dict:
    """Every minute: sweep lapsed holds. Notification sending and refund retries join here later."""
    from apps.bookings.services.booking_service import BookingService

    return {"holds_swept": BookingService().sweep_expired()}
