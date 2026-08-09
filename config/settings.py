"""
Django settings for the django-agent-ready-template starter.

Secure by default: DEBUG is off unless explicitly enabled, secrets come from the
environment (never the repo), and production security headers turn on
automatically when DEBUG is False. For local development, copy `.env.example` to
`.env` and set `DEBUG=True`.

See https://docs.djangoproject.com/en/6.1/ref/settings/
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
# All deployment-specific and secret values are read from the environment so
# nothing sensitive lives in the repo. `.env` is git-ignored; `.env.example`
# documents the available keys.
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

# SECURITY: keep DEBUG off by default. Enable it explicitly in local `.env`.
DEBUG = env("DEBUG")

# SECURITY: no hardcoded secret. A throwaway key is allowed only in DEBUG so a
# fresh clone runs immediately; production (DEBUG=False) requires a real one.
if DEBUG:
    SECRET_KEY = env("SECRET_KEY", default="dev-insecure-key-do-not-use-in-production")
else:
    SECRET_KEY = env("SECRET_KEY")

ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Defaults to SQLite so a fresh clone runs with zero setup. Point DATABASE_URL
# at PostgreSQL in production (e.g. postgres://user:pass@host:5432/dbname).
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
# Argon2 is the secure default password hasher even though the base template
# ships no login UI (the admin still authenticates). Add user accounts via the
# opt-in recipe in the README.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
# Source assets (including TypeScript-compiled JS) live under static/. Production
# collects them into STATIC_ROOT via `manage.py collectstatic`.
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Production security headers (active whenever DEBUG is False)
# ---------------------------------------------------------------------------
# These turn on automatically in production so a deploy is hardened without
# remembering to flip switches. Adjust HSTS duration only after confirming HTTPS
# is stable on your domain.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
