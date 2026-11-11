import re

import pytest
from django.core.cache import cache
from rest_framework.exceptions import Throttled

from apps.accounts.services.otp_service import OtpService
from apps.core.exceptions import ApiError

PHONE = "+919800000001"


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()


@pytest.fixture
def sent():
    return []


@pytest.fixture
def otp(sent):
    return OtpService(sms=lambda *, phone, text: sent.append(text))


def _code(sent):
    return re.search(r"\b(\d{6})\b", sent[-1]).group(1)


def test_request_then_verify_succeeds_once(otp, sent):
    otp.request(phone=PHONE)
    code = _code(sent)
    otp.verify(phone=PHONE, code=code)
    with pytest.raises(ApiError) as e:  # single use
        otp.verify(phone=PHONE, code=code)
    assert e.value.code == "OTP_EXPIRED"


def test_wrong_code_locks_after_max_attempts(otp, sent):
    otp.request(phone=PHONE)
    for _ in range(5):
        with pytest.raises(ApiError) as e:
            otp.verify(phone=PHONE, code="000000" if _code(sent) != "000000" else "111111")
        assert e.value.code == "OTP_INVALID"
    with pytest.raises(ApiError) as e:
        otp.verify(phone=PHONE, code=_code(sent))  # even the right code is refused now
    assert e.value.code == "OTP_LOCKED"


def test_resend_cooldown(otp, sent):
    otp.request(phone=PHONE)
    with pytest.raises(Throttled):
        otp.request(phone=PHONE)
