import json

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .mobile_api_serializers import (
    MobileDeviceRegistrationSerializer,
    MobileLoginSerializer,
    MobileServiceRequestSerializer,
)
from .models import MobileDevice, ServiceAppointment, ServiceMessage, ServiceRequest
from .views import (
    build_customer_snapshot_payload,
    build_provider_snapshot_payload,
    build_unread_message_map,
    create_activity_log,
    get_request_display_code,
    get_provider_for_user,
    publish_service_message_event,
    resolve_request_message_access,
    serialize_service_message,
)


def build_identity_payload(user):
    provider = get_provider_for_user(user)
    payload = {
        "id": user.id,
        "username": user.username,
        "email": user.email or "",
        "role": "provider" if provider else "customer",
        "provider": None,
        "customer_profile": None,
    }
    if provider:
        payload["provider"] = {
            "id": provider.id,
            "full_name": provider.full_name,
            "city": provider.city,
            "district": provider.district,
            "phone": provider.phone,
            "is_verified": bool(provider.is_verified),
            "rating": float(provider.rating or 0.0),
        }
    else:
        profile = getattr(user, "customer_profile", None)
        payload["customer_profile"] = {
            "phone": getattr(profile, "phone", "") if profile else "",
            "city": getattr(profile, "city", "") if profile else "",
            "district": getattr(profile, "district", "") if profile else "",
        }
    return payload


def drf_response_from_django_response(raw_response):
    if raw_response is None:
        return None
    if isinstance(raw_response, JsonResponse):
        try:
            decoded = raw_response.content.decode("utf-8") if raw_response.content else "{}"
            data = json.loads(decoded or "{}")
        except Exception:
            data = {"detail": "error"}
        return Response(data, status=raw_response.status_code)
    if isinstance(raw_response, HttpResponse):
        return Response({"detail": "error"}, status=raw_response.status_code)
    return Response({"detail": "error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MobileLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mobile_login"

    def post(self, request):
        serializer = MobileLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        provider = get_provider_for_user(user)

        if provider and not provider.is_verified:
            return Response(
                {"detail": "pending-approval", "message": "Usta hesabi admin onayi bekliyor."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        payload = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": build_identity_payload(user),
        }
        if provider:
            payload["snapshot"] = build_provider_snapshot_payload(provider)
        else:
            payload["snapshot"] = build_customer_snapshot_payload(user)
        return Response(payload, status=status.HTTP_200_OK)


class MobileMeView(APIView):
    def get(self, request):
        provider = get_provider_for_user(request.user)
        if provider and not provider.is_verified:
            return Response(
                {"detail": "pending-approval", "message": "Usta hesabi admin onayi bekliyor."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = {"user": build_identity_payload(request.user)}
        if provider:
            payload["snapshot"] = build_provider_snapshot_payload(provider)
        else:
            payload["snapshot"] = build_customer_snapshot_payload(request.user)
        return Response(payload, status=status.HTTP_200_OK)


class MobileCustomerRequestsView(APIView):
    def get(self, request):
        if get_provider_for_user(request.user):
            return Response({"detail": "forbidden-provider"}, status=status.HTTP_403_FORBIDDEN)

        status_filter = (request.GET.get("status") or "").strip()
        limit_raw = (request.GET.get("limit") or "20").strip()
        offset_raw = (request.GET.get("offset") or "0").strip()
        limit = min(100, max(1, int(limit_raw) if limit_raw.isdigit() else 20))
        offset = max(0, int(offset_raw) if offset_raw.isdigit() else 0)

        qs = (
            ServiceRequest.objects.filter(customer=request.user)
            .select_related("service_type", "matched_provider")
            .order_by("-created_at")
        )
        if status_filter:
            qs = qs.filter(status=status_filter)

        total_count = qs.count()
        page_items = list(qs[offset : offset + limit])
        request_ids = [item.id for item in page_items]
        unread_map = build_unread_message_map(request_ids, "customer")
        appointment_map = {
            item.service_request_id: item
            for item in ServiceAppointment.objects.filter(service_request_id__in=request_ids)
        }
        serialized = MobileServiceRequestSerializer(
            page_items,
            many=True,
            context={"unread_map": unread_map, "appointment_map": appointment_map},
        ).data
        return Response(
            {
                "count": total_count,
                "offset": offset,
                "limit": limit,
                "results": serialized,
            },
            status=status.HTTP_200_OK,
        )


class MobileProviderDashboardView(APIView):
    def get(self, request):
        provider = get_provider_for_user(request.user)
        if not provider:
            return Response({"detail": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
        if not provider.is_verified:
            return Response({"detail": "pending-approval"}, status=status.HTTP_403_FORBIDDEN)

        thread_limit_raw = (request.GET.get("thread_limit") or "20").strip()
        thread_limit = min(100, max(1, int(thread_limit_raw) if thread_limit_raw.isdigit() else 20))

        active_threads = list(
            provider.service_requests.filter(
                status="matched",
                matched_offer__isnull=False,
                matched_offer__provider=provider,
            )
            .select_related("service_type", "customer")
            .order_by("-created_at")[:thread_limit]
        )
        thread_ids = [item.id for item in active_threads]
        unread_map = build_unread_message_map(thread_ids, "provider")

        return Response(
            {
                "snapshot": build_provider_snapshot_payload(provider),
                "active_threads": [
                    {
                        "id": item.id,
                        "service_type": item.service_type.name,
                        "city": item.city,
                        "district": item.district,
                        "customer_name": item.customer_name,
                        "status": item.status,
                        "created_at": item.created_at,
                        "unread_messages": int(unread_map.get(item.id, 0)),
                    }
                    for item in active_threads
                ],
            },
            status=status.HTTP_200_OK,
        )


class MobileRequestMessagesView(APIView):
    def get(self, request, request_id):
        service_request, viewer_role, _back_url, blocked_response = resolve_request_message_access(
            request, request_id, api=True
        )
        if blocked_response:
            return drf_response_from_django_response(blocked_response)

        after_id_raw = (request.GET.get("after_id") or "").strip()
        after_id = int(after_id_raw) if after_id_raw.isdigit() else 0

        ServiceMessage.objects.filter(service_request=service_request, read_at__isnull=True).exclude(
            sender_role=viewer_role
        ).update(read_at=timezone.now())

        thread_qs = service_request.messages.select_related("sender_user").order_by("id")
        if after_id > 0:
            thread_qs = thread_qs.filter(id__gt=after_id)
        thread_messages = list(thread_qs[:100])
        latest_id = (
            thread_messages[-1].id
            if thread_messages
            else service_request.messages.order_by("-id").values_list("id", flat=True).first() or 0
        )
        return Response(
            {
                "messages": [serialize_service_message(item, viewer_role) for item in thread_messages],
                "latest_id": latest_id,
                "thread_closed": False,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, request_id):
        service_request, viewer_role, _back_url, blocked_response = resolve_request_message_access(
            request, request_id, api=True
        )
        if blocked_response:
            return drf_response_from_django_response(blocked_response)

        body = (request.data.get("body") or "").strip()
        if len(body) < 2:
            return Response({"detail": "Mesaj en az 2 karakter olmalidir."}, status=status.HTTP_400_BAD_REQUEST)
        if len(body) > 1000:
            return Response({"detail": "Mesaj en fazla 1000 karakter olabilir."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            message_item = ServiceMessage.objects.create(
                service_request=service_request,
                sender_user=request.user,
                sender_role=viewer_role,
                body=body,
            )
            create_activity_log(
                action_type="message_sent",
                service_request=service_request,
                message_item=message_item,
                actor_user=request.user,
                actor_role=viewer_role,
                source="user",
                summary=f"Talep {get_request_display_code(service_request)} icin yeni mesaj",
                note=body,
            )
        publish_service_message_event(message_item)
        return Response(
            {
                "ok": True,
                "message": serialize_service_message(message_item, viewer_role),
            },
            status=status.HTTP_201_CREATED,
        )


class MobileDeviceRegisterView(APIView):
    def post(self, request):
        serializer = MobileDeviceRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        platform = validated["platform"]
        device_id = validated["device_id"]
        push_token = validated.get("push_token")
        app_version = (validated.get("app_version") or "").strip()
        locale = (validated.get("locale") or "").strip()
        timezone_value = (validated.get("timezone") or "").strip()

        with transaction.atomic():
            if push_token:
                MobileDevice.objects.filter(push_token=push_token).exclude(
                    user=request.user,
                    platform=platform,
                    device_id=device_id,
                ).update(push_token=None)

            device, created = MobileDevice.objects.update_or_create(
                user=request.user,
                platform=platform,
                device_id=device_id,
                defaults={
                    "push_token": push_token,
                    "app_version": app_version,
                    "locale": locale,
                    "timezone": timezone_value,
                },
            )

        return Response(
            {
                "ok": True,
                "created": created,
                "device": {
                    "id": device.id,
                    "platform": device.platform,
                    "device_id": device.device_id,
                    "app_version": device.app_version,
                    "locale": device.locale,
                    "timezone": device.timezone,
                    "last_seen_at": device.last_seen_at,
                },
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
