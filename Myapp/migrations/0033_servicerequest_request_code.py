from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import get_random_string


REQUEST_CODE_PREFIX = "TLP"
REQUEST_CODE_RANDOM_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
REQUEST_CODE_RANDOM_LENGTH = 6


def _build_request_code(created_at, existing_codes):
    reference_date = created_at or timezone.now()
    date_part = reference_date.strftime("%Y%m%d")
    while True:
        random_part = get_random_string(REQUEST_CODE_RANDOM_LENGTH, allowed_chars=REQUEST_CODE_RANDOM_CHARS)
        candidate = f"{REQUEST_CODE_PREFIX}-{date_part}-{random_part}"
        if candidate not in existing_codes:
            existing_codes.add(candidate)
            return candidate


def populate_request_codes(apps, schema_editor):
    ServiceRequest = apps.get_model("Myapp", "ServiceRequest")
    existing_codes = set(
        ServiceRequest.objects.exclude(request_code__isnull=True)
        .exclude(request_code="")
        .values_list("request_code", flat=True)
    )
    pending = (
        ServiceRequest.objects.filter(Q(request_code__isnull=True) | Q(request_code=""))
        .only("id", "created_at")
        .order_by("id")
    )
    for item in pending.iterator(chunk_size=500):
        code = _build_request_code(item.created_at, existing_codes)
        ServiceRequest.objects.filter(id=item.id).update(request_code=code)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("Myapp", "0032_alter_servicerequest_details"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="request_code",
            field=models.CharField(blank=True, editable=False, max_length=24, null=True),
        ),
        migrations.RunPython(populate_request_codes, noop_reverse),
        migrations.AlterField(
            model_name="servicerequest",
            name="request_code",
            field=models.CharField(db_index=True, editable=False, max_length=24, unique=True),
        ),
    ]
