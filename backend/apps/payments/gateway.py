"""The only place that talks to Razorpay.

DEV SHORTCUT (project owner's call, until the 50% milestone): no network, orders are local ids and every
signature verifies.
shortcut: verifies nothing, so replace the bodies with razorpay.Client calls before any real money moves.
"""
import uuid


class PaymentGateway:
    def create_order(self, *, amount_paise: int, receipt: str) -> str:
        return f"order_dev_{uuid.uuid4().hex[:14]}"

    def verify_payment(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        return True

    def verify_webhook(self, *, body: bytes, signature: str) -> bool:
        return True
