import os
import subprocess
import sys


def env_bool(name, default=False):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}


def run(*args):
    print(">", " ".join(args))
    subprocess.run(args, check=True)


def main():
    python_executable = sys.executable

    run(python_executable, "manage.py", "collectstatic", "--noinput")

    if env_bool("VERCEL_RUN_MIGRATIONS", True):
        run(python_executable, "manage.py", "migrate", "--noinput")
    else:
        print("Skipping database migrations because VERCEL_RUN_MIGRATIONS is disabled.")

    if env_bool("AUTO_SUPERUSER_ENABLED", False):
        run(python_executable, "scripts/ensure_superuser.py")
    else:
        print("Skipping automatic superuser bootstrap because AUTO_SUPERUSER_ENABLED is disabled.")


if __name__ == "__main__":
    main()
