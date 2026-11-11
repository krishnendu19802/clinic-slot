import phonenumbers
from rest_framework import serializers

from .enums import Role
from .models import User


def normalize_phone(value: str) -> str:
    try:
        number = phonenumbers.parse(value, "IN")
    except phonenumbers.NumberParseException as e:
        raise serializers.ValidationError("Enter a valid mobile number") from e
    if not phonenumbers.is_valid_number(number):
        raise serializers.ValidationError("Enter a valid mobile number")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        return normalize_phone(super().to_internal_value(data))


class OtpRequestSerializer(serializers.Serializer):
    phone = PhoneField()
    role = serializers.ChoiceField(choices=Role.choices)


class OtpVerifySerializer(OtpRequestSerializer):
    otp = serializers.RegexField(r"^\d{6}$")


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="display_name", read_only=True)
    profile_complete = serializers.SerializerMethodField()
    doctor = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "role", "phone", "email", "name", "profile_complete", "doctor"]

    def get_profile_complete(self, user) -> bool:
        if user.role == Role.DOCTOR:  # a doctor is "complete" once they have submitted for review
            return user.doctor_profile.verification_status != "draft"
        return bool(user.display_name)

    def get_doctor(self, user):
        p = getattr(user, "doctor_profile", None)
        if not p:
            return None
        return {"id": p.id, "verification_status": p.verification_status, "status_reason": p.status_reason}


class MeUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, required=False)
    email = serializers.EmailField(required=False, allow_null=True)
