"""Simulated medical-registry website: random result, about 80% pass (PRD D4). No real lookup."""
import random

from apps.doctors.enums import RegistryCheck


class RegistryService:
    def __init__(self, rng=random.random, pass_rate: float = 0.8):
        self.rng, self.pass_rate = rng, pass_rate

    def check(self, *, registration_no: str, council_name: str) -> str:
        return RegistryCheck.PASSED if self.rng() < self.pass_rate else RegistryCheck.FAILED
