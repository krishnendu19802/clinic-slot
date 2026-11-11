from rest_framework.test import APIClient


def login(role: str, phone: str) -> APIClient:
    api = APIClient()
    api.post("/api/v1/auth/otp/request", {"phone": phone, "role": role}, format="json")
    r = api.post("/api/v1/auth/otp/verify", {"phone": phone, "role": role, "otp": "123456"}, format="json")
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return api
