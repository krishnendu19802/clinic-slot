from .settings import *  # noqa: F403

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
OTP_DEV_FIXED = True  # code is always 123456
import tempfile  # noqa: E402

MEDIA_ROOT = tempfile.mkdtemp(prefix="clinicslot-test-media-")
