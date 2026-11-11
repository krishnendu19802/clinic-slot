"""Browser end-to-end test of the patient journey against a real backend.

Creates a throwaway database, seeds two approved doctors, starts Django (8000) and Vite (5173), drives headless
Chrome through search -> login -> hold -> details -> pay -> confirmed -> my bookings, then cleans up.
Needs: Postgres (clinicslot role with CREATEDB), Redis, Google Chrome (CHROME_PATH to override).
Run from frontend/:  npm run e2e
"""
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BACKEND, DB = ROOT / "backend", "clinicslot_e2e"
PG = {**os.environ, "PGPASSWORD": "clinicslot"}
env = {**os.environ, "DATABASE_URL": f"postgres://clinicslot:clinicslot@localhost:5432/{DB}"}
py = str(BACKEND / ".venv/bin/python")


def sql(q):
    subprocess.run(["psql", "-h", "localhost", "-U", "clinicslot", "-d", "postgres", "-qc", q], env=PG, check=True,
                   capture_output=True)


def up(url):
    for _ in range(80):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


SEED = """
from tests.factories import make_doctor
make_doctor(phone='+919700000001', name='Dr A. Sen', fee=50000, exp=12, languages=['English','Bengali'])
make_doctor(phone='+919700000002', name='Dr R. Das', fee=40000, exp=7, lat='23.55', lng='87.35', area='Bidhannagar')
"""

APPROVE = """
from apps.doctors.models import DoctorProfile
from apps.doctors.services.verification_service import VerificationService
VerificationService().approve(profile=DoctorProfile.objects.get(user__phone='+919700000099'), actor=None)
"""

sql(f"DROP DATABASE IF EXISTS {DB}")
sql(f"CREATE DATABASE {DB}")
subprocess.run([py, "manage.py", "migrate", "-v0"], cwd=BACKEND, env=env, check=True)
subprocess.run([py, "manage.py", "shell", "-c", SEED], cwd=BACKEND, env=env, check=True, capture_output=True)
subprocess.run(["redis-cli", "-n", "1", "flushdb"], capture_output=True)  # clear OTP cooldowns from earlier runs

be = subprocess.Popen([py, "manage.py", "runserver", "8000", "--noreload"], cwd=BACKEND, env=env,
                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
# not via npx: terminating npx would orphan vite (and keep the output pipe open)
fe = subprocess.Popen([str(HERE.parent / "node_modules/.bin/vite"), "--host", "127.0.0.1", "--strictPort"], cwd=HERE.parent,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
rc = 1
try:
    assert up("http://127.0.0.1:8000/api/v1/policy") and up("http://127.0.0.1:5173/"), "servers did not start"
    shots = HERE / "shots"
    shots.mkdir(exist_ok=True)
    node = lambda script, *args: subprocess.run(["node", str(HERE / script), str(shots), *args], cwd=HERE.parent).returncode  # noqa: E731
    rc = node("doctor.mjs", "onboarding")
    if rc == 0:  # the admin approves the doctor who just submitted (the Django admin action calls this same service)
        subprocess.run([py, "manage.py", "shell", "-c", APPROVE], cwd=BACKEND, env=env, check=True, capture_output=True)
        subprocess.run(["redis-cli", "-n", "1", "flushdb"], capture_output=True)  # same phone logs in again: skip the 30 s OTP cooldown
        rc = node("doctor.mjs", "schedule")
    if rc == 0:
        subprocess.run(["redis-cli", "-n", "1", "flushdb"], capture_output=True)
        rc = node("patient.mjs")
finally:
    for p in (be, fe):
        p.terminate()
    log = be.communicate(timeout=10)[0]
    bad = [ln for ln in log.splitlines() if "Traceback" in ln or '" 500 ' in ln]
    print("backend tracebacks/500s:", len(bad))
    for ln in bad[:5]:
        print("  ", ln)
    sql(f"DROP DATABASE IF EXISTS {DB}")
sys.exit(rc or (1 if bad else 0))
