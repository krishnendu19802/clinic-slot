from collections import defaultdict

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.core import audit, platform
from apps.core.exceptions import ApiError
from apps.scheduling.enums import ExceptionType
from apps.scheduling.repo.psql.clinic_repo import ClinicRepo
from apps.scheduling.repo.psql.schedule_repo import ScheduleRepo
from apps.scheduling.services.slot_generation_service import GenerationResult, SlotGenerationService


def _minutes(start, end) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


class ScheduleService:
    def __init__(self, clinics=None, schedule=None, generator=None):
        self.clinics = clinics or ClinicRepo()
        self.schedule = schedule or ScheduleRepo()
        self.generator = generator or SlotGenerationService()

    def _clinic(self, *, user, clinic_id: int):
        clinic = self.clinics.get_for(doctor=user.doctor_profile, clinic_id=clinic_id)
        if not clinic:
            raise ApiError("NOT_FOUND", "Clinic not found", status_code=404)
        return clinic

    def get(self, *, user, clinic_id: int) -> dict:
        clinic = self._clinic(user=user, clinic_id=clinic_id)
        return {"windows": self.schedule.windows(clinic=clinic), "exceptions": self.schedule.exceptions(clinic=clinic)}

    @staticmethod
    def _normalise(*, windows: list[dict]) -> list[dict]:
        """Resolve slot length (minutes, or count, or platform default) and reject unusable windows."""
        errors, out = {}, []
        for i, w in enumerate(windows):
            span = _minutes(w["start_time"], w["end_time"])
            if span <= 0:
                errors[f"windows.{i}"] = ["End time must be after start time"]
                continue
            minutes = w.get("slot_minutes")
            if not minutes and w.get("slot_count"):
                minutes, rest = divmod(span, w["slot_count"])
                if rest:
                    errors[f"windows.{i}"] = [f"{w['slot_count']} slots do not divide {span} minutes evenly"]
                    continue
            minutes = minutes or platform.get("default_slot_minutes")
            if span % minutes:
                errors[f"windows.{i}"] = [f"{minutes}-minute slots do not divide the {span}-minute window"]
                continue
            out.append({"weekday": w["weekday"], "start_time": w["start_time"], "end_time": w["end_time"],
                        "slot_minutes": minutes})
        by_day = defaultdict(list)
        for w in out:
            by_day[w["weekday"]].append(w)
        for day, items in by_day.items():
            items.sort(key=lambda w: w["start_time"])
            if any(a["end_time"] > b["start_time"] for a, b in zip(items, items[1:], strict=False)):
                errors[f"weekday_{day}"] = ["Windows on the same day overlap"]
        if errors:
            raise ValidationError(errors)
        return out

    @transaction.atomic
    def replace(self, *, user, clinic_id: int, windows: list[dict]) -> GenerationResult:
        clinic = self.clinics.lock(clinic=self._clinic(user=user, clinic_id=clinic_id))
        self.schedule.replace_windows(clinic=clinic, windows=self._normalise(windows=windows))
        result = self.generator.generate(clinic=clinic)
        audit.log(actor=user, action="schedule.update", entity=clinic, generated=result.generated,
                  conflicts=len(result.conflicts))
        return result

    @transaction.atomic
    def add_exception(self, *, user, clinic_id: int, fields: dict) -> GenerationResult:
        clinic = self.clinics.lock(clinic=self._clinic(user=user, clinic_id=clinic_id))
        start, end = fields.get("start_time"), fields.get("end_time")
        if (start is None) != (end is None) or (start and end <= start):
            raise ValidationError({"start_time": ["Give both start and end, with end after start"]})
        if fields["type"] == ExceptionType.EXTRA and start is None:
            raise ValidationError({"start_time": ["An extra window needs start and end"]})
        if fields["type"] == ExceptionType.EXTRA:
            minutes = fields.get("slot_minutes") or platform.get("default_slot_minutes")
            if _minutes(start, end) % minutes:
                raise ValidationError({"slot_minutes": [f"{minutes}-minute slots do not divide the window"]})
        self.schedule.add_exception(clinic=clinic, fields=fields)
        return self.generator.generate(clinic=clinic)

    @transaction.atomic
    def remove_exception(self, *, user, clinic_id: int, exception_id: int) -> GenerationResult:
        clinic = self.clinics.lock(clinic=self._clinic(user=user, clinic_id=clinic_id))
        exception = self.schedule.get_exception(clinic=clinic, exception_id=exception_id)
        if not exception:
            raise ApiError("NOT_FOUND", "Exception not found", status_code=404)
        self.schedule.delete_exception(exception=exception)
        return self.generator.generate(clinic=clinic)
