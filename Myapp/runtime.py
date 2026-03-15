from django.conf import settings


def get_marketplace_lifecycle_mode():
    raw_mode = str(getattr(settings, "MARKETPLACE_LIFECYCLE_MODE", "scheduler") or "scheduler").strip().lower()
    if raw_mode in {"request", "scheduler"}:
        return raw_mode
    return "scheduler"


def is_scheduler_heartbeat_required():
    return get_marketplace_lifecycle_mode() == "scheduler"


def are_websockets_enabled():
    return bool(getattr(settings, "WEBSOCKETS_ENABLED", True))
