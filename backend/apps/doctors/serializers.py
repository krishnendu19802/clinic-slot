from rest_framework import serializers

from .enums import DocType
from .models import Council, DoctorDocument, DoctorProfile, Speciality

LANGUAGES = ["English", "Bengali", "Hindi"]


class CouncilSerializer(serializers.ModelSerializer):
    class Meta:
        model = Council
        fields = ["id", "name"]


class SpecialitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Speciality
        fields = ["id", "slug", "name", "blurb"]


class DoctorProfileSerializer(serializers.ModelSerializer):
    council_id = serializers.PrimaryKeyRelatedField(source="council", queryset=Council.objects.all(),
                                                    required=False, allow_null=True)
    specialities = serializers.PrimaryKeyRelatedField(queryset=Speciality.objects.all(), many=True, required=False)
    languages = serializers.ListField(child=serializers.ChoiceField(choices=LANGUAGES), required=False)

    class Meta:
        model = DoctorProfile
        fields = ["full_name", "gender", "registration_no", "council_id", "degrees", "specialities",
                  "experience_years", "fee_paise", "languages", "remarks",
                  "verification_status", "status_reason", "registry_check"]
        read_only_fields = ["verification_status", "status_reason", "registry_check"]
        # The auto unique-together validator would force council+registration_no on every PATCH;
        # duplicates are checked in ProfileService instead (the DB constraint stays as the backstop).
        validators: list = []

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["specialities"] = [s.pk for s in instance.specialities.all()]
        return data


class DocumentSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="original_name", read_only=True)
    type = serializers.ChoiceField(choices=DocType.choices)
    file = serializers.FileField(write_only=True)

    class Meta:
        model = DoctorDocument
        fields = ["id", "type", "name", "size_bytes", "uploaded_at", "file"]
        read_only_fields = ["id", "size_bytes", "uploaded_at"]
