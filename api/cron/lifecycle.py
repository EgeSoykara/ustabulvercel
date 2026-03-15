import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from io import StringIO
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Companywebsite.settings")

import django

django.setup()

from django.core.management import call_command


def is_authorized(headers):
    expected_secret = (os.getenv("CRON_SECRET") or "").strip()
    if not expected_secret:
        return True
    auth_header = (headers.get("authorization") or "").strip()
    return hmac.compare_digest(auth_header, f"Bearer {expected_secret}")


class handler(BaseHTTPRequestHandler):
    def send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def run_lifecycle_job(self):
        output = StringIO()
        try:
            call_command("marketplace_lifecycle", stdout=output, stderr=output)
        except Exception as exc:
            self.send_json(
                500,
                {
                    "ok": False,
                    "detail": "lifecycle-run-failed",
                    "error": str(exc),
                    "output": output.getvalue()[-2000:],
                },
            )
            return

        self.send_json(
            200,
            {
                "ok": True,
                "detail": "lifecycle-run-completed",
                "output": output.getvalue()[-2000:],
            },
        )

    def do_GET(self):
        if not is_authorized(self.headers):
            self.send_json(401, {"ok": False, "detail": "unauthorized"})
            return
        self.run_lifecycle_job()

    def do_POST(self):
        self.do_GET()
