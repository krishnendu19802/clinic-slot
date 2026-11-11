from apps.bookings.models import Booking
from apps.payments.enums import OrderStatus, PaymentStatus, RefundStatus
from apps.payments.models import Payment, PaymentOrder, Refund


class PaymentRepo:
    def open_order(self, *, booking: Booking) -> PaymentOrder | None:
        return PaymentOrder.objects.filter(booking=booking, status=OrderStatus.CREATED).order_by("-id").first()

    def create_order(self, *, booking: Booking, razorpay_order_id: str, amount_paise: int) -> PaymentOrder:
        return PaymentOrder.objects.create(booking=booking, razorpay_order_id=razorpay_order_id,
                                           amount_paise=amount_paise)

    def get_order(self, *, razorpay_order_id: str) -> PaymentOrder | None:
        return PaymentOrder.objects.select_related("booking").filter(razorpay_order_id=razorpay_order_id).first()

    def has_live_payment(self, *, booking: Booking) -> bool:
        return Payment.objects.filter(order__booking=booking,
                                      status__in=[PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED]).exists()

    def expire_open_orders(self, *, booking: Booking) -> None:
        PaymentOrder.objects.filter(booking=booking, status=OrderStatus.CREATED).update(status=OrderStatus.EXPIRED)

    def mark_order(self, *, order: PaymentOrder, status: str) -> None:
        order.status = status
        order.save(update_fields=["status"])

    def upsert_payment(self, *, order: PaymentOrder, razorpay_payment_id: str, status: str, amount_paise: int,
                       method: str, signature_verified: bool, raw: dict) -> Payment:
        payment, _ = Payment.objects.update_or_create(
            razorpay_payment_id=razorpay_payment_id,
            defaults={"order": order, "status": status, "amount_paise": amount_paise, "method": method,
                      "signature_verified": signature_verified, "raw": raw})
        return payment

    def create_refund(self, *, payment: Payment, booking: Booking, amount_paise: int, reason: str) -> Refund:
        return Refund.objects.create(payment=payment, booking=booking, amount_paise=amount_paise, reason=reason,
                                     status=RefundStatus.PENDING)
