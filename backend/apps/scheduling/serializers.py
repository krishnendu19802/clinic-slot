from rest_framework import serializers

from .enums import ExceptionType
from .models import Clinic, ScheduleException, ScheduleTemplate, Slot

TIME = {"format": "%H:%M", "input_formats": ["%H:%M", "%H:%M:%S"]}


class ClinicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = ["id", "name", "address", "area", "city", "pincode", "lat", "lng", "phone"]


class WindowInSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=1, max_value=7)
    start_time = serializers.TimeField(**TIME)
    end_time = serializers.TimeField(**TIME)
    slot_minutes = serializers.IntegerField(min_value=5, max_value=120, required=False)
    slot_count = serializers.IntegerField(min_value=1, max_value=100, required=False)


class ScheduleInSerializer(serializers.Serializer):
    windows = WindowInSerializer(many=True)


class WindowOutSerializer(serializers.ModelSerializer):
    start_time = serializers.TimeField(**TIME)
    end_time = serializers.TimeField(**TIME)
    slot_count = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleTemplate
        fields = ["id", "weekday", "start_time", "end_time", "slot_minutes", "slot_count"]

    def get_slot_count(self, w) -> int:
        span = (w.end_time.hour * 60 + w.end_time.minute) - (w.start_time.hour * 60 + w.start_time.minute)
        return span // w.slot_minutes


class ExceptionSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(choices=ExceptionType.choices)
    start_time = serializers.TimeField(required=False, allow_null=True, **TIME)
    end_time = serializers.TimeField(required=False, allow_null=True, **TIME)

    class Meta:
        model = ScheduleException
        fields = ["id", "date", "type", "start_time", "end_time", "slot_minutes"]


class DoctorSlotSerializer(serializers.ModelSerializer):
    start = serializers.DateTimeField(source="start_ts")
    end = serializers.DateTimeField(source="end_ts")

    class Meta:
        model = Slot
        fields = ["id", "start", "end", "seq", "token", "status"]
