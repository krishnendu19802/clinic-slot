from apps.scheduling.models import Clinic, ScheduleException, ScheduleTemplate


class ScheduleRepo:
    def windows(self, *, clinic: Clinic):
        return list(ScheduleTemplate.objects.filter(clinic=clinic).order_by("weekday", "start_time"))

    def replace_windows(self, *, clinic: Clinic, windows: list[dict]) -> None:
        ScheduleTemplate.objects.filter(clinic=clinic).delete()
        ScheduleTemplate.objects.bulk_create([ScheduleTemplate(clinic=clinic, **w) for w in windows])

    def exceptions(self, *, clinic: Clinic):
        return list(ScheduleException.objects.filter(clinic=clinic).order_by("date", "start_time"))

    def add_exception(self, *, clinic: Clinic, fields: dict) -> ScheduleException:
        return ScheduleException.objects.create(clinic=clinic, **fields)

    def get_exception(self, *, clinic: Clinic, exception_id: int) -> ScheduleException | None:
        return ScheduleException.objects.filter(clinic=clinic, pk=exception_id).first()

    def delete_exception(self, *, exception: ScheduleException) -> None:
        exception.delete()
