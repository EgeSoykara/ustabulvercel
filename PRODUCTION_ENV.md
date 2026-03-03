# Production Environment Notes

## Focus and completion checklist

1. Web service ayakta olmali (`gunicorn` + static dosyalar).
2. Worker surekli calismali (lifecycle scheduler).
3. Veritabani kalici olmali (PostgreSQL / `DATABASE_URL`).
4. Health endpoint takip edilmeli (`/health/lifecycle/`).

## Render deployment (recommended)

Bu repo artik `render.yaml` icerir. Render'da:

1. `New +` -> `Blueprint` sec.
2. Repo'yu bagla.
3. Render, `ustabul-web`, `ustabul-lifecycle-worker` ve `ustabul-db` kaynaklarini olusturur.
4. Deploy tamamlaninca migration otomatik calisir.

## Required environment variables

`render.yaml` bir cogunu set eder. Ek olarak dashboard uzerinden kontrol et:

```bash
DJANGO_ENV=production
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<strong-random-secret>
RENDER_EXTERNAL_HOSTNAME=<your-app.onrender.com>
USE_X_FORWARDED_HOST=1
SECURE_SSL_REDIRECT=1
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=1
SECURE_HSTS_PRELOAD=1
DATABASE_URL=<render-postgres-connection-string>
MOBILE_LOGIN_RATE_LIMIT=20/minute
LIFECYCLE_HEALTH_TOKEN=<long-random-token>
LIFECYCLE_LOCK_TTL_SECONDS=120
APPOINTMENT_SLOT_BUFFER_MINUTES=45
```

## Health check

Worker'in surekli calistigini asagidaki endpoint ile izle:

```bash
GET /health/lifecycle/ (header: X-Health-Token: <LIFECYCLE_HEALTH_TOKEN>)
```

- `200`: healthy
- `503`: stale veya heartbeat yok

## Local quick start

```bash
cp .env.local.example .env
python manage.py migrate
python manage.py runserver
```

Worker localde:

```bash
python manage.py marketplace_lifecycle --loop --interval 30
```
