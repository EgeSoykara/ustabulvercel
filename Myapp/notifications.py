from collections import defaultdict
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import (
    NotificationCursor,
    Provider,
    ServiceAppointment,
    ServiceMessage,
    ServiceRequest,
    WorkflowEvent,
    WorkflowEventRead,
)


REQUEST_STATUS_LABELS = dict(ServiceRequest.STATUS_CHOICES)
APPOINTMENT_STATUS_LABELS = dict(ServiceAppointment.STATUS_CHOICES)
PROVIDER_CACHE_ATTR = "_provider_profile_cache"
NOTIFICATION_CENTER_LIMIT = 50
NOTIFICATION_CATEGORY_ORDER = ("message", "request", "appointment")
NOTIFICATION_CATEGORY_META = {
    "message": {
        "label": "Mesajlar",
        "description": "Yeni sohbetler ve yanıtlar.",
    },
    "request": {
        "label": "Talep Durumu",
        "description": "Teklif, eşleşme ve talep durumu güncellemeleri.",
    },
    "appointment": {
        "label": "Randevu",
        "description": "Randevu oluşturma, onay ve tamamlama adımları.",
    },
}


def _truncate(text, max_len=180):
    value = str(text or "").strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "..."


def get_notification_retention_days():
    try:
        configured = int(getattr(settings, "NOTIFICATION_RETENTION_DAYS", 30))
    except (TypeError, ValueError):
        configured = 30
    return max(7, configured)


def get_notification_cutoff(now=None, *, days=None, include_all=False):
    if include_all:
        return None

    reference = now or timezone.now()
    if days is None:
        days = get_notification_retention_days()
    try:
        normalized_days = max(1, int(days))
    except (TypeError, ValueError):
        normalized_days = get_notification_retention_days()
    return reference - timedelta(days=normalized_days)


def get_provider_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if hasattr(user, PROVIDER_CACHE_ATTR):
        return getattr(user, PROVIDER_CACHE_ATTR)
    provider = Provider.objects.filter(user_id=user.id).only("id").first()
    setattr(user, PROVIDER_CACHE_ATTR, provider)
    return provider


def get_notification_cursor(user, *, create=False):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if create:
        cursor, _created = NotificationCursor.objects.get_or_create(
            user=user,
            defaults={"workflow_seen_at": None},
        )
        return cursor
    return NotificationCursor.objects.filter(user=user).only(
        "id",
        "workflow_seen_at",
        "allow_message_notifications",
        "allow_request_notifications",
        "allow_appointment_notifications",
    ).first()


def get_notification_preferences(user=None, *, cursor=None):
    current_cursor = cursor
    if current_cursor is None and user is not None:
        current_cursor = get_notification_cursor(user, create=False)
    return {
        "message": bool(getattr(current_cursor, "allow_message_notifications", True)),
        "request": bool(getattr(current_cursor, "allow_request_notifications", True)),
        "appointment": bool(getattr(current_cursor, "allow_appointment_notifications", True)),
    }


def get_enabled_notification_categories(preferences):
    return {
        category_key
        for category_key in NOTIFICATION_CATEGORY_ORDER
        if preferences.get(category_key, True)
    }


def invalidate_unread_notifications_cache(*user_refs):
    cache_keys = []
    seen_user_ids = set()
    for ref in user_refs:
        if ref is None:
            continue
        user_id = getattr(ref, "id", ref)
        try:
            normalized_id = int(user_id)
        except (TypeError, ValueError):
            continue
        if normalized_id <= 0 or normalized_id in seen_user_ids:
            continue
        seen_user_ids.add(normalized_id)
        cache_keys.append(f"notif:unread:{normalized_id}")
    if cache_keys:
        cache.delete_many(cache_keys)


def parse_notification_entry_id(entry_id):
    raw_value = str(entry_id or "").strip().lower()
    if raw_value.startswith("msg-") and raw_value[4:].isdigit():
        return ("message", int(raw_value[4:]))
    if raw_value.startswith("wf-") and raw_value[3:].isdigit():
        return ("workflow", int(raw_value[3:]))
    return (None, None)


def normalize_notification_category(raw_value):
    value = str(raw_value or "").strip().lower()
    if value in {"message", "request", "appointment"}:
        return value
    return "all"


def get_incoming_message_queryset(user, provider=None, now=None, *, days=None, include_all=False):
    cutoff = get_notification_cutoff(now, days=days, include_all=include_all)
    if provider:
        queryset = ServiceMessage.objects.filter(
            service_request__matched_provider=provider,
            service_request__matched_offer__isnull=False,
            service_request__matched_offer__provider=provider,
            service_request__status="matched",
        ).exclude(sender_role="provider")
    else:
        queryset = ServiceMessage.objects.filter(
            service_request__customer=user,
            service_request__matched_offer__isnull=False,
            service_request__status="matched",
        ).exclude(sender_role="customer")

    if cutoff is not None:
        queryset = queryset.filter(created_at__gte=cutoff)
    return queryset


def get_workflow_event_queryset(user, provider=None, now=None, *, days=None, include_all=False):
    cutoff = get_notification_cutoff(now, days=days, include_all=include_all)
    if provider:
        queryset = WorkflowEvent.objects.filter(
            Q(service_request__matched_provider=provider)
            | Q(appointment__provider=provider)
            | Q(service_request__provider_offers__provider=provider)
        ).distinct()
    else:
        queryset = WorkflowEvent.objects.filter(service_request__customer=user)

    if cutoff is not None:
        queryset = queryset.filter(created_at__gte=cutoff)
    return queryset


def get_notification_panel_url(user, provider=None):
    current_provider = provider if provider is not None else get_provider_for_user(user)
    return reverse("provider_requests") if current_provider else reverse("my_requests")


def workflow_event_category_key(event):
    return "appointment" if event.target_type == "appointment" else "request"


def dedupe_workflow_events(events):
    deduped_events = []
    seen_event_keys = set()
    for event in events:
        event_key = (
            event.target_type,
            event.service_request_id,
            event.appointment_id,
            event.to_status,
        )
        if event_key in seen_event_keys:
            continue
        seen_event_keys.add(event_key)
        deduped_events.append(event)
    return deduped_events


def get_notification_workflow_events(
    user,
    provider=None,
    now=None,
    *,
    limit=None,
    days=None,
    include_all=False,
    preferences=None,
):
    enabled_categories = get_enabled_notification_categories(preferences or get_notification_preferences(user))
    workflow_qs = (
        get_workflow_event_queryset(user, provider=provider, now=now, days=days, include_all=include_all)
        .exclude(actor_user=user)
        .select_related("service_request", "appointment", "actor_user", "appointment__service_request")
        .order_by("-created_at", "-id")
    )
    if limit is not None:
        workflow_qs = workflow_qs[:limit]

    events = []
    for event in dedupe_workflow_events(list(workflow_qs)):
        if workflow_event_category_key(event) in enabled_categories:
            events.append(event)
    return events


def get_read_workflow_event_ids(user, workflow_event_ids):
    if not workflow_event_ids:
        return set()
    return set(
        WorkflowEventRead.objects.filter(user=user, workflow_event_id__in=workflow_event_ids).values_list(
            "workflow_event_id",
            flat=True,
        )
    )


def is_workflow_event_unread(event, read_workflow_ids, workflow_seen_at):
    if event.id in read_workflow_ids:
        return False
    if workflow_seen_at and event.created_at <= workflow_seen_at:
        return False
    return True


def get_unread_workflow_event_ids(user, provider=None, now=None, *, preferences=None):
    cursor = get_notification_cursor(user, create=False)
    workflow_seen_at = cursor.workflow_seen_at if cursor else None
    events = get_notification_workflow_events(
        user,
        provider=provider,
        now=now,
        preferences=preferences,
    )
    if not events:
        return []

    read_ids = get_read_workflow_event_ids(user, [event.id for event in events])
    return [
        event.id
        for event in events
        if is_workflow_event_unread(event, read_ids, workflow_seen_at)
    ]


def get_total_unread_notifications_count(user):
    if not user or not getattr(user, "is_authenticated", False):
        return 0

    cache_seconds = max(1, int(getattr(settings, "NOTIFICATION_UNREAD_CACHE_SECONDS", 6)))
    cache_key = f"notif:unread:{user.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return int(cached)

    now = timezone.now()
    provider = get_provider_for_user(user)
    cursor = get_notification_cursor(user, create=False)
    preferences = get_notification_preferences(cursor=cursor)

    unread_messages_count = 0
    if preferences["message"]:
        unread_messages_count = (
            get_incoming_message_queryset(user, provider=provider, now=now)
            .filter(read_at__isnull=True)
            .count()
        )

    unread_workflow_count = len(
        get_unread_workflow_event_ids(
            user,
            provider=provider,
            now=now,
            preferences=preferences,
        )
    )

    total_unread = unread_messages_count + unread_workflow_count
    cache.set(cache_key, total_unread, timeout=cache_seconds)
    return total_unread


def mark_all_notifications_read(user):
    if not user or not getattr(user, "is_authenticated", False):
        return {"message_count": 0, "workflow_count": 0, "unread_notifications_count": 0}

    provider = get_provider_for_user(user)
    now = timezone.now()
    marked_message_count = (
        get_incoming_message_queryset(user, provider=provider, now=now)
        .filter(read_at__isnull=True)
        .update(read_at=now)
    )

    cursor = get_notification_cursor(user, create=True)
    preferences = get_notification_preferences(cursor=cursor)
    unread_workflow_ids = get_unread_workflow_event_ids(
        user,
        provider=provider,
        now=now,
        preferences=preferences,
    )
    if unread_workflow_ids:
        WorkflowEventRead.objects.bulk_create(
            [WorkflowEventRead(user=user, workflow_event_id=event_id) for event_id in unread_workflow_ids],
            ignore_conflicts=True,
        )
    cursor.workflow_seen_at = now
    cursor.save(update_fields=["workflow_seen_at", "updated_at"])

    invalidate_unread_notifications_cache(user)
    return {
        "message_count": marked_message_count,
        "workflow_count": len(unread_workflow_ids),
        "unread_notifications_count": get_total_unread_notifications_count(user),
    }


def _event_status_label(event, raw_status):
    if event.target_type == "appointment":
        return APPOINTMENT_STATUS_LABELS.get(raw_status, raw_status or "-")
    return REQUEST_STATUS_LABELS.get(raw_status, raw_status or "-")


def get_notification_category_meta(category_key):
    return NOTIFICATION_CATEGORY_META.get(
        category_key,
        {
            "label": "Diğer",
            "description": "Diğer bildirimler.",
        },
    )


def build_workflow_notification_link(user, event, provider=None):
    panel_url = get_notification_panel_url(user, provider=provider)
    service_request_id = event.service_request_id
    if not service_request_id and event.appointment_id and getattr(event.appointment, "service_request_id", None):
        service_request_id = event.appointment.service_request_id
    if not service_request_id:
        return panel_url

    params = {"highlight_request": service_request_id}
    hash_target = f"#request-card-{service_request_id}"

    if provider:
        if event.target_type == "appointment" and event.to_status == "pending":
            hash_target = f"#pending-appointment-card-{service_request_id}"
            params["highlight_appointment"] = event.appointment_id or ""
        elif event.to_status == "pending_provider":
            hash_target = f"#pending-offer-card-{service_request_id}"
        elif event.to_status == "pending_customer":
            hash_target = f"#waiting-selection-card-{service_request_id}"
        else:
            hash_target = f"#active-thread-card-{service_request_id}"

    return f"{panel_url}?{urlencode(params)}{hash_target}"


def resolve_notification_entry(user, entry_id):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    kind, object_id = parse_notification_entry_id(entry_id)
    if not kind or not object_id:
        return None

    now = timezone.now()
    provider = get_provider_for_user(user)
    cursor = get_notification_cursor(user, create=False)
    workflow_seen_at = cursor.workflow_seen_at if cursor else None

    if kind == "message":
        message = (
            get_incoming_message_queryset(user, provider=provider, now=now, include_all=True)
            .select_related("service_request")
            .filter(id=object_id)
            .first()
        )
        if not message:
            return None
        return {
            "entry_id": f"msg-{message.id}",
            "kind": "message",
            "object_id": message.id,
            "link": reverse("request_messages", args=[message.service_request_id]),
            "is_unread": message.read_at is None,
        }

    workflow_event = (
        get_workflow_event_queryset(user, provider=provider, now=now, include_all=True)
        .exclude(actor_user=user)
        .select_related("appointment", "appointment__service_request")
        .filter(id=object_id)
        .first()
    )
    if not workflow_event:
        return None

    read_workflow_ids = get_read_workflow_event_ids(user, [workflow_event.id])
    return {
        "entry_id": f"wf-{workflow_event.id}",
        "kind": "workflow",
        "object_id": workflow_event.id,
        "link": build_workflow_notification_link(user, workflow_event, provider=provider),
        "is_unread": is_workflow_event_unread(workflow_event, read_workflow_ids, workflow_seen_at),
    }


def mark_notification_entry_read(user, entry_id):
    resolved = resolve_notification_entry(user, entry_id)
    if not resolved:
        return None

    now = timezone.now()
    provider = get_provider_for_user(user)
    marked = False

    if resolved["kind"] == "message":
        marked = bool(
            get_incoming_message_queryset(user, provider=provider, now=now, include_all=True)
            .filter(id=resolved["object_id"], read_at__isnull=True)
            .update(read_at=now)
        )
    else:
        _read_marker, created = WorkflowEventRead.objects.get_or_create(
            user=user,
            workflow_event_id=resolved["object_id"],
        )
        marked = created

    invalidate_unread_notifications_cache(user)
    resolved["marked"] = marked
    resolved["is_unread"] = False
    resolved["unread_notifications_count"] = get_total_unread_notifications_count(user)
    return resolved


def build_notification_entries(user, *, limit=NOTIFICATION_CENTER_LIMIT, days=None, include_all=False, unread_only=False):
    if not user or not getattr(user, "is_authenticated", False):
        return []

    now = timezone.now()
    provider = get_provider_for_user(user)
    cursor = get_notification_cursor(user, create=False)
    preferences = get_notification_preferences(cursor=cursor)
    workflow_seen_at = cursor.workflow_seen_at if cursor else None

    entries = []

    if preferences["message"]:
        message_category = get_notification_category_meta("message")
        message_queryset = (
            get_incoming_message_queryset(
                user,
                provider=provider,
                now=now,
                days=days,
                include_all=include_all,
            )
            .select_related("service_request")
            .order_by("-created_at")
        )
        if unread_only:
            message_queryset = message_queryset.filter(read_at__isnull=True)
        messages = list(message_queryset[:limit])
        for item in messages:
            request_code = item.service_request.display_code if item.service_request_id else "-"
            entries.append(
                {
                    "entry_id": f"msg-{item.id}",
                    "kind": "message",
                    "category_key": "message",
                    "category": message_category["label"],
                    "category_description": message_category["description"],
                    "title": f"Talep {request_code} için yeni mesaj",
                    "body": _truncate(item.body, 220),
                    "link": reverse("request_messages", args=[item.service_request_id]),
                    "open_link": reverse("notifications_open_entry", args=[f"msg-{item.id}"]),
                    "mark_read_url": reverse("notifications_mark_entry_read", args=[f"msg-{item.id}"]),
                    "created_at": item.created_at,
                    "is_unread": item.read_at is None,
                }
            )

    deduped_events = get_notification_workflow_events(
        user,
        provider=provider,
        now=now,
        limit=None if unread_only else limit,
        days=days,
        include_all=include_all,
        preferences=preferences,
    )
    read_workflow_event_ids = get_read_workflow_event_ids(user, [event.id for event in deduped_events])
    for event in deduped_events:
        is_unread = is_workflow_event_unread(event, read_workflow_event_ids, workflow_seen_at)
        if unread_only and not is_unread:
            continue
        to_label = _event_status_label(event, event.to_status)
        from_label = _event_status_label(event, event.from_status)
        target_label = "Randevu" if event.target_type == "appointment" else "Talep"
        category_key = workflow_event_category_key(event)
        category_meta = get_notification_category_meta(category_key)
        if event.note:
            body = _truncate(event.note, 220)
        else:
            body = f"{from_label} -> {to_label}"
        entries.append(
            {
                "entry_id": f"wf-{event.id}",
                "kind": "workflow",
                "category_key": category_key,
                "category": category_meta["label"],
                "category_description": category_meta["description"],
                "title": f"{target_label} durumu güncellendi: {to_label}",
                "body": body,
                "link": build_workflow_notification_link(user, event, provider=provider),
                "open_link": reverse("notifications_open_entry", args=[f"wf-{event.id}"]),
                "mark_read_url": reverse("notifications_mark_entry_read", args=[f"wf-{event.id}"]),
                "created_at": event.created_at,
                "is_unread": is_unread,
            }
        )

    entries.sort(key=lambda item: item["created_at"], reverse=True)
    return entries[:limit]


def build_notification_sections(entries):
    grouped_entries = defaultdict(list)
    for entry in entries:
        grouped_entries[entry.get("category_key") or "other"].append(entry)

    sections = []
    for category_key in NOTIFICATION_CATEGORY_ORDER:
        items = grouped_entries.pop(category_key, [])
        if not items:
            continue
        category_meta = get_notification_category_meta(category_key)
        sections.append(
            {
                "key": category_key,
                "label": category_meta["label"],
                "description": category_meta["description"],
                "items": items,
                "unread_count": sum(1 for item in items if item.get("is_unread")),
            }
        )

    for category_key, items in grouped_entries.items():
        category_meta = get_notification_category_meta(category_key)
        sections.append(
            {
                "key": category_key,
                "label": category_meta["label"],
                "description": category_meta["description"],
                "items": items,
                "unread_count": sum(1 for item in items if item.get("is_unread")),
            }
        )

    return sections
