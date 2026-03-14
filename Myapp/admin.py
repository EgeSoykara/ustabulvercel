from django import forms
from django.contrib import admin
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .constants import NC_CITY_CHOICES, NC_DISTRICT_CHOICES
from .models import (
    ActivityLog,
    CustomerProfile,
    ErrorLog,
    IdempotencyRecord,
    MobileDevice,
    NotificationCursor,
    Provider,
    ProviderAvailabilitySlot,
    ProviderOffer,
    ProviderRating,
    SchedulerHeartbeat,
    ServiceAppointment,
    ServiceMessage,
    ServiceRequest,
    ServiceType,
    WorkflowEvent,
    WorkflowEventRead,
)


def with_existing_choice(choices, current_value):
    if current_value and current_value not in [value for value, _ in choices]:
        return choices + [(current_value, f"{current_value} (Mevcut)")]
    return choices


class ProviderAdminForm(forms.ModelForm):
    city = forms.ChoiceField(choices=NC_CITY_CHOICES, label="Şehir")
    district = forms.ChoiceField(choices=NC_DISTRICT_CHOICES, label="İlçe")

    class Meta:
        model = Provider
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        city_value = self.instance.city if self.instance and self.instance.pk else None
        district_value = self.instance.district if self.instance and self.instance.pk else None
        self.fields["city"].choices = with_existing_choice(list(NC_CITY_CHOICES), city_value)
        self.fields["district"].choices = with_existing_choice(list(NC_DISTRICT_CHOICES), district_value)


class ServiceRequestAdminForm(forms.ModelForm):
    city = forms.ChoiceField(choices=NC_CITY_CHOICES, label="Şehir")
    district = forms.ChoiceField(choices=NC_DISTRICT_CHOICES, label="İlçe")

    class Meta:
        model = ServiceRequest
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        city_value = self.instance.city if self.instance and self.instance.pk else None
        district_value = self.instance.district if self.instance and self.instance.pk else None
        self.fields["city"].choices = with_existing_choice(list(NC_CITY_CHOICES), city_value)
        self.fields["district"].choices = with_existing_choice(list(NC_DISTRICT_CHOICES), district_value)


class CustomerProfileAdminForm(forms.ModelForm):
    city = forms.ChoiceField(choices=[("", "Şehir seçin")] + NC_CITY_CHOICES, required=False, label="Şehir")
    district = forms.ChoiceField(choices=[("", "İlçe seçin")] + NC_DISTRICT_CHOICES, required=False, label="İlçe")

    class Meta:
        model = CustomerProfile
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        city_value = self.instance.city if self.instance and self.instance.pk else None
        district_value = self.instance.district if self.instance and self.instance.pk else None
        self.fields["city"].choices = with_existing_choice([("", "Şehir seçin")] + list(NC_CITY_CHOICES), city_value)
        self.fields["district"].choices = with_existing_choice([("", "İlçe seçin")] + list(NC_DISTRICT_CHOICES), district_value)


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    form = ProviderAdminForm
    list_display = (
        "full_name",
        "user",
        "service_types_list",
        "city",
        "district",
        "phone",
        "latitude",
        "longitude",
        "is_available",
        "is_verified",
        "verified_at",
        "rating",
    )
    list_filter = ("service_types", "city", "is_available", "is_verified")
    search_fields = ("full_name", "user__username", "city", "district", "phone", "service_types__name")
    filter_horizontal = ("service_types",)

    @admin.display(description="Hizmet Türleri")
    def service_types_list(self, obj):
        return obj.service_types_display()


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    form = ServiceRequestAdminForm
    list_display = (
        "request_code",
        "customer_name",
        "customer",
        "service_type",
        "city",
        "district",
        "status",
        "matched_provider",
        "matched_offer",
        "matched_at",
        "created_at",
    )
    list_filter = ("status", "service_type", "city")
    search_fields = ("request_code", "customer_name", "customer_phone", "city", "district")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    form = CustomerProfileAdminForm
    list_display = ("user", "phone", "city", "district", "created_at")
    search_fields = ("user__username", "phone", "city", "district")


@admin.register(ProviderRating)
class ProviderRatingAdmin(admin.ModelAdmin):
    list_display = ("service_request", "provider", "customer", "score", "updated_at")
    list_filter = ("score", "provider__city")
    search_fields = (
        "service_request__id",
        "service_request__request_code",
        "provider__full_name",
        "customer__username",
        "comment",
    )


@admin.register(ProviderOffer)
class ProviderOfferAdmin(admin.ModelAdmin):
    list_display = (
        "service_request",
        "provider",
        "sequence",
        "status",
        "expires_at",
        "reminder_sent_at",
        "token",
        "sent_at",
        "responded_at",
    )
    list_filter = ("status", "provider__city")
    search_fields = (
        "service_request__id",
        "service_request__request_code",
        "provider__full_name",
        "token",
        "last_delivery_detail",
        "quote_note",
    )


@admin.register(ServiceAppointment)
class ServiceAppointmentAdmin(admin.ModelAdmin):
    list_display = ("service_request", "provider", "customer", "scheduled_for", "status", "updated_at")
    list_filter = ("status", "provider__city")
    search_fields = (
        "service_request__id",
        "service_request__request_code",
        "provider__full_name",
        "customer__username",
        "customer_note",
        "provider_note",
    )


@admin.register(ProviderAvailabilitySlot)
class ProviderAvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ("provider", "weekday", "start_time", "end_time", "is_active", "updated_at")
    list_filter = ("weekday", "is_active", "provider__city")
    search_fields = ("provider__full_name", "provider__user__username")


@admin.register(ServiceMessage)
class ServiceMessageAdmin(admin.ModelAdmin):
    list_display = ("service_request", "sender_user", "sender_role", "created_at", "read_at")
    list_filter = ("sender_role",)
    search_fields = ("service_request__id", "service_request__request_code", "sender_user__username", "body")


@admin.register(WorkflowEvent)
class WorkflowEventAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "target_type",
        "service_request",
        "appointment",
        "from_status",
        "to_status",
        "actor_role",
        "actor_user",
        "source",
        "note",
    )
    list_filter = ("target_type", "actor_role", "source", "from_status", "to_status", "created_at")
    search_fields = (
        "service_request__id",
        "service_request__request_code",
        "appointment__id",
        "actor_user__username",
        "note",
    )
    list_select_related = ("service_request", "appointment", "actor_user")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    readonly_fields = (
        "target_type",
        "service_request",
        "appointment",
        "from_status",
        "to_status",
        "actor_user",
        "actor_role",
        "source",
        "note",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "action_type",
        "service_request",
        "appointment",
        "message",
        "actor_role",
        "actor_user",
        "source",
        "summary",
        "note",
    )
    list_filter = ("action_type", "actor_role", "source", "created_at")
    search_fields = (
        "service_request__id",
        "service_request__request_code",
        "appointment__id",
        "message__id",
        "actor_user__username",
        "summary",
        "note",
    )
    list_select_related = ("service_request", "appointment", "message", "actor_user")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    readonly_fields = (
        "action_type",
        "service_request",
        "appointment",
        "message",
        "actor_user",
        "actor_role",
        "source",
        "summary",
        "note",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = ("created_at", "scope", "endpoint", "user", "key_short")
    list_filter = ("scope", "created_at")
    search_fields = ("scope", "endpoint", "user__username", "key")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    readonly_fields = ("key", "scope", "endpoint", "user", "created_at")
    actions = ("purge_records_older_than_2_days",)

    @admin.display(description="Anahtar")
    def key_short(self, obj):
        return f"{obj.key[:12]}..."

    @admin.action(description="2 günden eski kayıtları temizle")
    def purge_records_older_than_2_days(self, request, queryset):
        cutoff = timezone.now() - timedelta(days=2)
        deleted_count, _ = IdempotencyRecord.objects.filter(created_at__lt=cutoff).delete()
        self.message_user(request, f"{deleted_count} idempotency kaydı temizlendi.", level=messages.SUCCESS)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SchedulerHeartbeat)
class SchedulerHeartbeatAdmin(admin.ModelAdmin):
    list_display = (
        "worker_name",
        "run_count",
        "last_started_at",
        "last_success_at",
        "last_error_at",
        "healthy",
        "updated_at",
    )
    list_filter = ("updated_at", "last_error_at")
    search_fields = ("worker_name", "last_error")
    ordering = ("worker_name",)
    readonly_fields = (
        "worker_name",
        "run_count",
        "last_started_at",
        "last_success_at",
        "last_error_at",
        "last_error",
        "updated_at",
    )

    @admin.display(boolean=True, description="Sağlıklı")
    def healthy(self, obj):
        stale_after = max(10, int(getattr(settings, "LIFECYCLE_HEARTBEAT_STALE_SECONDS", 180)))
        reference_at = obj.last_success_at or obj.last_started_at or obj.updated_at
        if not reference_at:
            return False
        age_seconds = (timezone.now() - reference_at).total_seconds()
        return age_seconds <= stale_after

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(NotificationCursor)
class NotificationCursorAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "allow_message_notifications",
        "allow_request_notifications",
        "allow_appointment_notifications",
        "workflow_seen_at",
        "updated_at",
    )
    search_fields = ("user__username",)
    ordering = ("-updated_at",)
    readonly_fields = ("user", "workflow_seen_at", "created_at", "updated_at")
    list_filter = (
        "allow_message_notifications",
        "allow_request_notifications",
        "allow_appointment_notifications",
        "updated_at",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "user",
                    "allow_message_notifications",
                    "allow_request_notifications",
                    "allow_appointment_notifications",
                    "workflow_seen_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return False


@admin.register(WorkflowEventRead)
class WorkflowEventReadAdmin(admin.ModelAdmin):
    list_display = ("user", "workflow_event", "read_at")
    list_filter = ("read_at", "workflow_event__target_type")
    search_fields = (
        "user__username",
        "workflow_event__service_request__request_code",
        "workflow_event__note",
    )
    ordering = ("-read_at", "-id")
    autocomplete_fields = ("user", "workflow_event")


@admin.register(MobileDevice)
class MobileDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "device_id", "app_version", "locale", "timezone", "last_seen_at")
    list_filter = ("platform", "last_seen_at")
    search_fields = ("user__username", "device_id", "push_token")
    readonly_fields = ("created_at", "last_seen_at")
    ordering = ("-last_seen_at", "-id")


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "status_code",
        "method",
        "path",
        "user",
        "request_id",
        "is_resolved",
    )
    list_filter = ("status_code", "method", "resolved_at", "created_at")
    search_fields = ("path", "message", "traceback", "request_id", "user__username", "ip_address")
    readonly_fields = (
        "created_at",
        "path",
        "method",
        "status_code",
        "message",
        "traceback",
        "request_id",
        "ip_address",
        "user_agent",
        "user",
    )
    ordering = ("-created_at", "-id")
    actions = ("mark_resolved", "mark_unresolved")
    date_hierarchy = "created_at"

    @admin.action(description="Seçilen kayıtları çözüldü olarak işaretle")
    def mark_resolved(self, request, queryset):
        updated_count = queryset.filter(resolved_at__isnull=True).update(resolved_at=timezone.now())
        self.message_user(request, f"{updated_count} kayıt çözüldü olarak işaretlendi.", level=messages.SUCCESS)

    @admin.action(description="Seçilen kayıtları tekrar açık yap")
    def mark_unresolved(self, request, queryset):
        updated_count = queryset.filter(resolved_at__isnull=False).update(resolved_at=None)
        self.message_user(request, f"{updated_count} kayıt tekrar açık duruma alındı.", level=messages.SUCCESS)

    def has_add_permission(self, request):
        return False
