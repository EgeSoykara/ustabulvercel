# Vercel Deployment Notes

## What changed for Vercel

This repo now includes:

- `api/index.py`: Django WSGI entrypoint for the Vercel Python Runtime
- `api/cron/lifecycle.py`: optional lifecycle trigger endpoint for Vercel Cron Jobs or external schedulers
- `vercel.json`: serverless routing, static fallback, function duration, and bundle exclusions
- `scripts/vercel_build.py`: build hook for `collectstatic`, `migrate`, and optional superuser bootstrap

## Important platform notes

1. Vercel does not support long-running workers the way Render does.
2. WebSocket support is not available for this Django deployment model on Vercel.
3. The project now defaults to `MARKETPLACE_LIFECYCLE_MODE=request` on Vercel:
   time-based marketplace transitions are refreshed during normal HTTP requests.
4. Chat already has polling fallback, so messaging still works without WebSockets.

## Required environment variables

Use `.env.vercel.example` as the baseline.

Minimum required values:

- `DJANGO_ENV=production`
- `DJANGO_DEBUG=0`
- `DJANGO_SECRET_KEY=<strong random value>`
- `DATABASE_URL=<postgres connection string>`

Recommended:

- `USE_WHITENOISE=0`
- `WEBSOCKETS_ENABLED=0`
- `MARKETPLACE_LIFECYCLE_MODE=request`
- `AUTO_SUPERUSER_ENABLED=1`
- `LIFECYCLE_HEALTH_TOKEN=<secret>`
- `CRON_SECRET=<secret if you plan to use cron>`

## Deploy steps

1. Create a Vercel project from this repository.
2. Add a Postgres database connection through `DATABASE_URL`.
3. Add the environment variables from `.env.vercel.example`.
4. Deploy.

Builds will run:

- `python manage.py collectstatic --noinput`
- `python manage.py migrate --noinput`
- `python scripts/ensure_superuser.py` when `AUTO_SUPERUSER_ENABLED=1`

## Static files

- Source static files under `static/` are served directly by Vercel.
- Django admin static files are collected into `staticfiles/` during build.
- `vercel.json` rewrites `/static/*` requests to `staticfiles/*` when needed.

## Optional cron setup

If you are on Pro or Enterprise, you can add a cron job for:

- `/api/cron/lifecycle`

Example `vercel.json` snippet:

```json
{
  "crons": [
    {
      "path": "/api/cron/lifecycle",
      "schedule": "*/5 * * * *"
    }
  ]
}
```

`CRON_SECRET` is automatically sent by Vercel as an `Authorization: Bearer ...` header.

## Hobby plan caveat

Vercel Hobby cron jobs can only run once per day, so frequent lifecycle scheduling is not practical there.
On Hobby, keep the default request-driven lifecycle mode or use an external scheduler to call `/api/cron/lifecycle`.
