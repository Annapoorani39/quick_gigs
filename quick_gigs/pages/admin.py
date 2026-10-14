from django.contrib import admin, messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import UserProfile, VerificationDocument, Gig, Application, Rating


# -------------------------
# Inline: show documents on profile page
# -------------------------
class VerificationDocumentInline(admin.TabularInline):
    model = VerificationDocument
    extra = 0
    readonly_fields = ("document_type", "file", "uploaded_at")
    can_delete = False


# -------------------------
# UserProfile Admin
# -------------------------
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    inlines = [VerificationDocumentInline]

    list_display = (
        "full_name",
        "email",
        "account_type",
        "verification_status",
        "aadhaar_verified",
        "submitted_at",
        "verified_at",
    )
    list_filter = ("verification_status", "account_type", "aadhaar_verified")
    search_fields = ("full_name", "user__username", "user__email", "phone_number")
    ordering = ("-submitted_at",)

    readonly_fields = ("submitted_at", "updated_at", "verified_at")

    fieldsets = (
        ("User", {"fields": ("user", "full_name", "phone_number", "account_type", "skills", "profile_photo")}),
        ("Aadhaar", {"fields": ("aadhaar_name", "aadhaar_verified")}),
        ("Verification", {"fields": ("verification_status", "rejection_reason", "admin_notes", "verified_at")}),
        ("Timestamps", {"fields": ("submitted_at", "updated_at")}),
    )

    actions = ("approve_selected", "reject_selected", "mark_aadhaar_verified")

    def email(self, obj):
        return obj.user.email
    email.short_description = "Email"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        should_be_active = obj.verification_status == "approved"
        if obj.user.is_active != should_be_active:
            obj.user.is_active = should_be_active
            obj.user.save(update_fields=["is_active"])

    @admin.action(description="✅ Approve selected profiles (activate login)")
    def approve_selected(self, request, queryset):
        count = 0
        for profile in queryset:
            profile.verification_status = "approved"
            profile.rejection_reason = ""
            profile.verified_at = timezone.now()
            profile.save(update_fields=["verification_status", "rejection_reason", "verified_at", "updated_at"])

            if not profile.user.is_active:
                profile.user.is_active = True
                profile.user.save(update_fields=["is_active"])

            if profile.user.email:
                send_mail(
                    subject="SkillMatch AI – Account Approved",
                    message=(
                        f"Hi {profile.full_name},\n\n"
                        "Your SkillMatch AI account has been approved ✅\n"
                        "You can now log in and start using the platform.\n\n"
                        "Regards,\nSkillMatch AI Team"
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[profile.user.email],
                    fail_silently=True,
                )

            count += 1

        self.message_user(request, f"Approved {count} profile(s).", level=messages.SUCCESS)

    @admin.action(description="❌ Reject selected profiles (deactivate login)")
    def reject_selected(self, request, queryset):
        count = 0
        for profile in queryset:
            profile.verification_status = "rejected"
            if not profile.rejection_reason:
                profile.rejection_reason = "Documents did not meet verification requirements."
            profile.verified_at = timezone.now()
            profile.save(update_fields=["verification_status", "rejection_reason", "verified_at", "updated_at"])

            if profile.user.is_active:
                profile.user.is_active = False
                profile.user.save(update_fields=["is_active"])

            if profile.user.email:
                send_mail(
                    subject="SkillMatch AI – Account Rejected",
                    message=(
                        f"Hi {profile.full_name},\n\n"
                        "Unfortunately, your SkillMatch AI verification was rejected ❌\n\n"
                        f"Reason:\n{profile.rejection_reason}\n\n"
                        "You can resubmit with correct documents.\n\n"
                        "Regards,\nSkillMatch AI Team"
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[profile.user.email],
                    fail_silently=True,
                )

            count += 1

        self.message_user(request, f"Rejected {count} profile(s).", level=messages.WARNING)

    @admin.action(description="🪪 Mark Aadhaar Verified = True")
    def mark_aadhaar_verified(self, request, queryset):
        updated = queryset.update(aadhaar_verified=True, updated_at=timezone.now())
        self.message_user(request, f"Marked Aadhaar verified for {updated} profile(s).", level=messages.SUCCESS)


# -------------------------
# VerificationDocument Admin
# -------------------------
@admin.register(VerificationDocument)
class VerificationDocumentAdmin(admin.ModelAdmin):
    list_display = ("user_profile", "document_type", "filename", "uploaded_at")
    list_filter = ("document_type", "uploaded_at")
    search_fields = ("user_profile__full_name", "user_profile__user__email")
    ordering = ("-uploaded_at",)

    def filename(self, obj):
        return obj.filename()
    filename.short_description = "File"


# -------------------------
# Gig Admin
# -------------------------
@admin.register(Gig)
class GigAdmin(admin.ModelAdmin):
    list_display = ("title", "employer", "status", "pay", "location", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "employer__username", "employer__email", "location")
    ordering = ("-created_at",)


# -------------------------
# Application Admin
# -------------------------
@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "gig",
        "applicant",
        "status",
        "proposed_pay",
        "payment_method",
        "worker_rated_employer",
        "employer_rated_worker",
        "applied_at",
    )
    list_filter = ("status", "payment_method", "worker_rated_employer", "employer_rated_worker", "applied_at")
    search_fields = ("gig__title", "applicant__username", "applicant__email")
    ordering = ("-applied_at",)


# -------------------------
# Rating Admin (NEW)
# -------------------------
@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("rating_type", "rated_user", "rater", "stars", "gig", "application", "created_at")
    list_filter = ("rating_type", "stars", "created_at")
    search_fields = ("rated_user__username", "rater__username", "comment")
    ordering = ("-created_at",)
