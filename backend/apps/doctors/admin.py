from django.contrib import admin, messages

from apps.core.exceptions import ApiError

from .models import Council, DoctorDocument, DoctorProfile, Speciality
from .services.verification_service import VerificationService


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ["full_name", "registration_no", "council", "verification_status", "registry_check", "submitted_at"]
    list_filter = ["verification_status", "registry_check"]
    search_fields = ["full_name", "registration_no", "user__phone"]
    actions = ["approve"]

    @admin.action(description="Approve selected doctors (go live and generate slots)")
    def approve(self, request, queryset):
        service = VerificationService()
        for profile in queryset:
            try:
                n = service.approve(profile=profile, actor=request.user)
                self.message_user(request, f"{profile.full_name}: approved, {n} slots generated")
            except ApiError as e:
                self.message_user(request, f"{profile.full_name}: {e.detail}", level=messages.ERROR)


admin.site.register([Council, Speciality, DoctorDocument])
