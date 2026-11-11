from .settings import *  # noqa: F403

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
OTP_DEV_FIXED = True  # code is always 123456
