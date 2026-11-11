from django.utils import timezone
from rest_framework import serializers

from apps.accounts.serializers import normalize_phone
from apps.doctors.enums import Gender
from apps.payments.enums import PaymentStatus, RefundStatus

from .enums import BookingStatus
from .models import Booking
from .policy import reschedule_block

BLOCK_TEXT = {"not_confirmed": "Only confirmed upcoming bookings can be rescheduled",
              "within_free_cancel_window": "Too close to the appointment to reschedule",
              "max_reschedules": "This booking was already rescheduled"}


class PatientDetailsSerializer(serializers.Serializer):
    is_self = serializers.BooleanField()
    name = serializers.CharField(max_length=120)
    age = serializers.IntegerField(min_value=0, max_value=120)
    gender = serializers.ChoiceField(choices=Gender.values)
    phone = serializers.CharField()
    reason = serializers.CharField(max_length=250, required=False, allow_blank=True, default="")

    def validate_phone(self, value):
        return normalize_phone(value)


class BookingDetailsInSerializer(serializers.Serializer):
    patient = PatientDetailsSerializer()


class BookingCreateSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()


class BookingSerializer(serializers.ModelSerializer):
    ref = serializers.CharField(read_only=True)
    server_time = serializers.SerializerMethodField()
    token = serializers.IntegerField(source="slot.token")
    slot = serializers.SerializerMethodField()
    doctor = serializers.SerializerMethodField()
    clinic = serializers.SerializerMethodField()
    patient = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_reschedule = serializers.SerializerMethodField()
    reschedule_blocked_reason = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    refund = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = ["id", "ref", "status", "server_time", "hold_expires_at", "token", "slot", "doctor", "clinic",
                  "patient", "fee_paise", "can_cancel", "can_reschedule", "reschedule_blocked_reason",
                  "payment_status", "refund", "cancelled_by", "cancel_reason"]

    def get_server_time(self, b):
        return timezone.now()

    def get_slot(self, b):
        s = b.slot
        return {"id": s.pk, "start": s.start_ts, "end": s.end_ts, "seq": s.seq, "window_total": s.window_total}

    def get_doctor(self, b):
        d = b.slot.clinic.doctor
        return {"id": d.pk, "name": d.full_name}

    def get_clinic(self, b):
        c = b.slot.clinic
        return {"id": c.pk, "name": c.name, "address": c.address, "area": c.area, "city": c.city,
                "lat": float(c.lat), "lng": float(c.lng), "phone": c.phone}

    def get_patient(self, b):
        if not b.patient_name:
            return None  # still at the Details step
        return {"is_self": b.is_self, "name": b.patient_name, "age": b.patient_age, "gender": b.patient_gender,
                "phone": b.patient_phone, "reason": b.reason}

    def get_can_cancel(self, b) -> bool:
        return b.status == BookingStatus.CONFIRMED and b.slot.start_ts > timezone.now()

    def _block(self, b):
        return reschedule_block(booking=b, now=timezone.now())

    def get_can_reschedule(self, b) -> bool:
        return self._block(b) is None

    def get_reschedule_blocked_reason(self, b):
        code = self._block(b)
        return {"code": code, "text": BLOCK_TEXT[code]} if code else None

    def _refunds(self, b):
        return sorted(b.refunds.all(), key=lambda r: r.pk)

    def get_payment_status(self, b):
        refunds = self._refunds(b)
        if refunds:
            return "refunded" if refunds[-1].status == RefundStatus.PROCESSED else "refund_pending"
        paid = any(p.status == PaymentStatus.CAPTURED for o in b.orders.all() for p in o.payments.all())
        return "paid" if paid else None

    def get_refund(self, b):
        refunds = self._refunds(b)
        return {"amount_paise": refunds[-1].amount_paise, "status": refunds[-1].status} if refunds else None
