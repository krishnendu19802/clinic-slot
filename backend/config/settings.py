from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-key-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # btree_gist / array fields
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "apps.core",
    "apps.accounts",
    "apps.doctors",
    "apps.scheduling",
    "apps.bookings",
    "apps.payments",
    "apps.notifications",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# Not ATOMIC_REQUESTS: services own their transactions so gateway calls never run inside one.
DATABASES = {"default": env.db("DATABASE_URL", default="postgres://clinicslot:clinicslot@localhost:5432/clinicslot")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

CACHES = {"default": env.cache("REDIS_URL", default="redis://localhost:6379/1")}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"  # clinic time zone; DB stays UTC
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "private_media"  # documents: never served statically

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.Pagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "apps.core.exceptions.handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {"otp": "20/hour", "booking": "30/minute"},
}
SPECTACULAR_SETTINGS = {"TITLE": "ClinicSlot API", "VERSION": "1.2"}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
REFRESH_COOKIE = "refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"
REFRESH_COOKIE_SECURE = not DEBUG

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"])
CORS_ALLOW_CREDENTIALS = True

# OTP / SMS
SMS_BACKEND = env("SMS_BACKEND", default="console")  # console | (real provider later)
OTP_DEV_FIXED = env.bool("OTP_DEV_FIXED", default=DEBUG)  # accept 123456 in dev
OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_SECONDS = 30
OTP_MAX_SENDS_PER_HOUR = 5

# Razorpay (test mode)
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="rzp_test_dummy")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="dummy")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="dummy")

# Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "tick": {"task": "apps.core.tasks.tick", "schedule": 60.0},
    "generate-slots": {"task": "apps.scheduling.tasks.generate_slots", "schedule": 86400.0},
    "reconcile": {"task": "apps.payments.tasks.reconcile", "schedule": 86400.0},
}
