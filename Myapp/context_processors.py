from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import SchedulerHeartbeat, ServiceAppointment, ServiceRequest, WorkflowEvent
from .notifications import get_total_unread_notifications_count
from .runtime import get_marketplace_lifecycle_mode, is_scheduler_heartbeat_required


def admin_operational_summary(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated or not request.user.is_staff:
        return {}
    if not request.path.startswith("/admin"):
        return {}

    stale_after_seconds = max(10, int(getattr(settings, "LIFECYCLE_HEARTBEAT_STALE_SECONDS", 180)))
    now = timezone.now()
    heartbeat = SchedulerHeartbeat.objects.filter(worker_name="marketplace_lifecycle").first()
    scheduler_mode = get_marketplace_lifecycle_mode()
    scheduler_required = is_scheduler_heartbeat_required()
    reference_at = None
    healthy = not scheduler_required
    age_seconds = None
    if heartbeat is not None:
        reference_at = heartbeat.last_success_at or heartbeat.last_started_at or heartbeat.updated_at
        if reference_at is not None:
            age_seconds = max(0, int((now - reference_at).total_seconds()))
            if scheduler_required:
                healthy = age_seconds <= stale_after_seconds

    summary = {
        "scheduler_healthy": healthy,
        "scheduler_run_count": heartbeat.run_count if heartbeat else 0,
        "scheduler_last_success_at": heartbeat.last_success_at if heartbeat else None,
        "scheduler_last_error": heartbeat.last_error if heartbeat else "",
        "scheduler_age_seconds": age_seconds,
        "scheduler_mode": scheduler_mode,
        "scheduler_required": scheduler_required,
        "events_last_hour": WorkflowEvent.objects.filter(created_at__gte=now - timedelta(hours=1)).count(),
        "open_requests": ServiceRequest.objects.filter(status__in=["new", "pending_provider", "pending_customer"]).count(),
        "open_appointments": ServiceAppointment.objects.filter(status__in=["pending", "pending_customer"]).count(),
    }
    return {"admin_ops_summary": summary}


def user_notifications_summary(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"nav_unread_notifications_count": 0}
    return {"nav_unread_notifications_count": get_total_unread_notifications_count(user)}
