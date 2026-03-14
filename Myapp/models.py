from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Avg
from django.utils.crypto import get_random_string
from django.utils import timezone

REQUEST_CODE_PREFIX = "TLP"
REQUEST_CODE_RANDOM_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
REQUEST_CODE_RANDOM_LENGTH = 6


def build_service_request_code(created_at=None):
    reference_date = created_at or timezone.now()
    date_part = reference_date.strftime("%Y%m%d")
    random_part = get_random_string(REQUEST_CODE_RANDOM_LENGTH, allowed_chars=REQUEST_CODE_RANDOM_CHARS)
    return f"{REQUEST_CODE_PREFIX}-{date_part}-{random_part}"


class ServiceType(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Provider(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="provider_profile",
    )
    full_name = models.CharField(max_length=120)
    service_types = models.ManyToManyField(ServiceType, related_name="providers", blank=True)
    city = models.CharField(max_length=80)
    district = models.CharField(max_length=80)
    phone = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=5.0)
    is_available = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_available", "-rating", "full_name"]

    def __str__(self):
        return self.full_name

    def service_types_display(self):
        return ", ".join(self.service_types.values_list("name", flat=True))

    def save(self, *args, **kwargs):
        if self.is_verified and self.verified_at is None:
            self.verified_at = timezone.now()
        if not self.is_verified and self.verified_at is not None:
            self.verified_at = None
        super().save(*args, **kwargs)


class ServiceRequest(models.Model):
    STATUS_CHOICES = (
        ("new", "Yeni"),
        ("pending_provider", "Usta Onayı Bekleniyor"),
        ("pending_customer", "Müşteri Seçimi Bekleniyor"),
        ("matched", "Eşleştirildi"),
        ("completed", "Tamamlandı"),
        ("cancelled", "İptal Edildi"),
    )

    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=20)
    city = models.CharField(max_length=80)
    district = models.CharField(max_length=80)
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name="requests")
    details = models.TextField(max_length=1000)
    request_code = models.CharField(max_length=24, unique=True, db_index=True, editable=False)
    created_ip = models.CharField(max_length=64, blank=True, default="", db_index=True)
    request_fingerprint = models.CharField(max_length=64, blank=True, default="", db_index=True)
    matched_provider = models.ForeignKey(
        Provider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_requests",
    )
    preferred_provider = models.ForeignKey(
        Provider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preferred_service_requests",
    )
    matched_offer = models.ForeignKey(
        "ProviderOffer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matched_requests",
    )
    matched_at = models.DateTimeField(null=True, blank=True)
    customer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_requests",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def display_code(self):
        if self.request_code:
            return self.request_code
        if self.id:
            return f"{REQUEST_CODE_PREFIX}-{self.id}"
        return REQUEST_CODE_PREFIX

    def _generate_unique_request_code(self):
        for _ in range(8):
            candidate = build_service_request_code(self.created_at)
            if not ServiceRequest.objects.filter(request_code=candidate).exists():
                return candidate
        raise ValidationError("Talep kodu üretilemedi. Lütfen tekrar deneyin.")

    def save(self, *args, **kwargs):
        if not self.request_code:
            self.request_code = self._generate_unique_request_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.display_code} - {self.customer_name} - {self.service_type.name}"


class ServiceAppointment(models.Model):
    STATUS_CHOICES = (
        ("pending", "Usta Onayı Bekleniyor"),
        ("pending_customer", "Müşteri Onayı Bekleniyor"),
        ("confirmed", "Onaylandı"),
        ("rejected", "Reddedildi"),
        ("cancelled", "Müşteri İptal Etti"),
        ("completed", "Tamamlandı"),
    )

    service_request = models.OneToOneField(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name="appointment",
    )
    customer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    scheduled_for = models.DateTimeField()
    customer_note = models.TextField(blank=True)
    provider_note = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_for"]

    def __str__(self):
        request_label = self.service_request.display_code if self.service_request_id else "-"
        return f"Randevu #{self.id} Talep {request_label} ({self.status})"


class ProviderOffer(models.Model):
    STATUS_CHOICES = (
        ("pending", "Beklemede"),
        ("accepted", "Kabul"),
        ("rejected", "Red"),
        ("expired", "Süre Doldu"),
        ("failed", "Gönderim Başarısız"),
    )

    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name="provider_offers")
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="offers")
    token = models.CharField(max_length=24, unique=True)
    sequence = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    quote_note = models.CharField(max_length=240, blank=True)
    last_delivery_detail = models.CharField(max_length=120, blank=True)
    sent_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["service_request_id", "sequence"]
        unique_together = ("service_request", "provider")

    def __str__(self):
        request_label = self.service_request.display_code if self.service_request_id else "-"
        return f"Talep {request_label} -> {self.provider.full_name} ({self.status})"




class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")
    phone = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=80, blank=True)
    district = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username



class ProviderRating(models.Model):
    SCORE_CHOICES = (
        (1, "1"),
        (2, "2"),
        (3, "3"),
        (4, "4"),
        (5, "5"),
    )

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="ratings")
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="provider_ratings")
    service_request = models.OneToOneField(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name="provider_rating",
        null=True,
        blank=True,
    )
    score = models.PositiveSmallIntegerField(choices=SCORE_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        request_label = self.service_request.display_code if self.service_request_id else "N/A"
        return f"{self.customer.username} -> {self.provider.full_name} / Talep {request_label}: {self.score}"

    @staticmethod
    def refresh_provider_average(provider_id):
        avg_score = (
            ProviderRating.objects.filter(provider_id=provider_id)
            .aggregate(avg_value=Avg("score"))
            .get("avg_value")
        )
        Provider.objects.filter(id=provider_id).update(rating=round(avg_score, 1) if avg_score is not None else 0.0)

    def save(self, *args, **kwargs):
        previous_provider_id = None
        if self.pk:
            previous_provider_id = (
                ProviderRating.objects.filter(pk=self.pk).values_list("provider_id", flat=True).first()
            )
        super().save(*args, **kwargs)
        ProviderRating.refresh_provider_average(self.provider_id)
        if previous_provider_id and previous_provider_id != self.provider_id:
            ProviderRating.refresh_provider_average(previous_provider_id)

    def delete(self, *args, **kwargs):
        provider_id = self.provider_id
        super().delete(*args, **kwargs)
        ProviderRating.refresh_provider_average(provider_id)


class ServiceMessage(models.Model):
    SENDER_ROLE_CHOICES = (
        ("customer", "Müşteri"),
        ("provider", "Usta"),
    )

    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name="messages")
    sender_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="service_messages")
    sender_role = models.CharField(max_length=20, choices=SENDER_ROLE_CHOICES)
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        request_label = self.service_request.display_code if self.service_request_id else "-"
        return f"Mesaj #{self.id} Talep {request_label} ({self.sender_role})"


class WorkflowEvent(models.Model):
    TARGET_CHOICES = (
        ("request", "Talep"),
        ("appointment", "Randevu"),
    )
    ACTOR_ROLE_CHOICES = (
        ("customer", "Müşteri"),
        ("provider", "Usta"),
        ("system", "Sistem"),
    )
    SOURCE_CHOICES = (
        ("user", "Kullanıcı"),
        ("scheduler", "Zamanlayıcı"),
        ("system", "Sistem"),
    )

    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES)
    service_request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_events",
    )
    appointment = models.ForeignKey(
        ServiceAppointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_events",
    )
    from_status = models.CharField(max_length=30)
    to_status = models.CharField(max_length=30)
    actor_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_events",
    )
    actor_role = models.CharField(max_length=20, choices=ACTOR_ROLE_CHOICES, default="system")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="system")
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.target_type} {self.from_status} -> {self.to_status}"


class WorkflowEventRead(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workflow_event_reads")
    workflow_event = models.ForeignKey(WorkflowEvent, on_delete=models.CASCADE, related_name="read_entries")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-read_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "workflow_event"], name="unique_workflow_event_read"),
        ]
        indexes = [
            models.Index(fields=["user", "read_at"]),
            models.Index(fields=["workflow_event", "user"]),
        ]

    def __str__(self):
        return f"{self.user.username} read workflow #{self.workflow_event_id}"


class ActivityLog(models.Model):
    ACTION_CHOICES = (
        ("request_status", "Talep Durum Degisimi"),
        ("appointment_status", "Randevu Durum Degisimi"),
        ("message_sent", "Mesaj Gonderildi"),
    )
    ACTOR_ROLE_CHOICES = (
        ("customer", "Musteri"),
        ("provider", "Usta"),
        ("system", "Sistem"),
    )
    SOURCE_CHOICES = (
        ("user", "Kullanici"),
        ("scheduler", "Zamanlayici"),
        ("system", "Sistem"),
    )

    action_type = models.CharField(max_length=32, choices=ACTION_CHOICES)
    service_request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    appointment = models.ForeignKey(
        ServiceAppointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    message = models.ForeignKey(
        ServiceMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    actor_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    actor_role = models.CharField(max_length=20, choices=ACTOR_ROLE_CHOICES, default="system")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="system")
    summary = models.CharField(max_length=240)
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["action_type", "created_at"]),
            models.Index(fields=["service_request", "created_at"]),
            models.Index(fields=["appointment", "created_at"]),
            models.Index(fields=["actor_user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action_type} @ {self.created_at:%Y-%m-%d %H:%M:%S}"


class IdempotencyRecord(models.Model):
    key = models.CharField(max_length=64, unique=True)
    scope = models.CharField(max_length=80)
    endpoint = models.CharField(max_length=200, blank=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="idempotency_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.scope} {self.created_at:%Y-%m-%d %H:%M:%S}"


class SchedulerHeartbeat(models.Model):
    worker_name = models.CharField(max_length=80, unique=True)
    run_count = models.PositiveIntegerField(default=0)
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=240, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["worker_name"]

    def __str__(self):
        return f"{self.worker_name} ({self.run_count})"


class SchedulerLock(models.Model):
    worker_name = models.CharField(max_length=80, unique=True)
    lock_owner = models.CharField(max_length=64, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_acquired_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["worker_name"]

    def __str__(self):
        return f"{self.worker_name} lock"


class NotificationCursor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="notification_cursor")
    workflow_seen_at = models.DateTimeField(null=True, blank=True)
    allow_message_notifications = models.BooleanField(default=True)
    allow_request_notifications = models.BooleanField(default=True)
    allow_appointment_notifications = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.username} cursor"


class MobileDevice(models.Model):
    PLATFORM_CHOICES = (
        ("ios", "iOS"),
        ("android", "Android"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="mobile_devices",
    )
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES)
    device_id = models.CharField(max_length=120)
    push_token = models.CharField(max_length=255, unique=True, null=True, blank=True)
    app_version = models.CharField(max_length=40, blank=True)
    locale = models.CharField(max_length=32, blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen_at", "-id"]
        unique_together = ("user", "platform", "device_id")
        indexes = [
            models.Index(fields=["user", "last_seen_at"]),
            models.Index(fields=["platform", "last_seen_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} {self.platform} {self.device_id}"


class ProviderAvailabilitySlot(models.Model):
    WEEKDAY_CHOICES = (
        (0, "Pazartesi"),
        (1, "Salı"),
        (2, "Çarşamba"),
        (3, "Perşembe"),
        (4, "Cuma"),
        (5, "Cumartesi"),
        (6, "Pazar"),
    )

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="availability_slots")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider_id", "weekday", "start_time"]
        unique_together = ("provider", "weekday", "start_time", "end_time")

    def __str__(self):
        return f"{self.provider.full_name} {self.get_weekday_display()} {self.start_time}-{self.end_time}"

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError("Bitiş saati başlangıç saatinden sonra olmalıdır.")

class ErrorLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    path = models.CharField(max_length=300, blank=True)
    method = models.CharField(max_length=10, blank=True)
    status_code = models.PositiveSmallIntegerField(default=500)
    message = models.CharField(max_length=500)
    traceback = models.TextField(blank=True)
    request_id = models.CharField(max_length=120, blank=True, db_index=True)
    ip_address = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="error_logs",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status_code", "created_at"]),
            models.Index(fields=["resolved_at", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.status_code} {self.message[:80]}"

    @property
    def is_resolved(self):
        return self.resolved_at is not None
