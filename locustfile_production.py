"""
Rico Hunt Production Load Testing - Real API Endpoints
Tests actual Rico API endpoints with realistic traffic patterns

Usage:
  Smoke:   locust -f locustfile_production.py -u 20 -r 5 --run-time 2m --headless
  Normal:  locust -f locustfile_production.py -u 100 -r 10 --run-time 10m --headless
  Peak:    locust -f locustfile_production.py -u 300 -r 30 --run-time 15m --headless
  Stress:  locust -f locustfile_production.py RicoHighLoadStress -u 500 -r 50 --run-time 10m --headless
  Web UI:  locust -f locustfile_production.py --web-host=0.0.0.0 --web-port=8089

Required env vars for auth tests:
  RICO_TEST_EMAIL=test@example.com
  RICO_TEST_PASSWORD=yourpassword
"""

import os
import random
import threading
import uuid
from collections import defaultdict
from datetime import datetime

from locust import HttpUser, between, events, task

HOST = "https://rico-job-automation-api.onrender.com"
TEST_EMAIL = os.getenv("RICO_TEST_EMAIL", "")
TEST_PASSWORD = os.getenv("RICO_TEST_PASSWORD", "")

# Thread-safe metrics
_lock = threading.Lock()
_response_times: list[float] = []
_error_counts: dict[str, int] = defaultdict(int)
_total_requests = 0
_total_failures = 0


def _record_time(elapsed_seconds: float) -> None:
    with _lock:
        _response_times.append(elapsed_seconds)


def _record_error(endpoint: str, status_code: int) -> None:
    with _lock:
        _error_counts[f"{endpoint}:{status_code}"] += 1


def _op_id() -> str:
    """Generate a valid operation_id (min_length=8, max_length=80)."""
    return uuid.uuid4().hex[:16]


class RicoPublicUser(HttpUser):
    """
    Simulates unauthenticated visitors — landing page, public chat, health checks.
    70% of simulated traffic.
    """
    wait_time = between(3, 8)
    host = HOST
    weight = 70

    def on_start(self):
        self.session_id = f"public_{random.randint(100_000, 999_999)}"

    # --- health / meta ---

    @task(20)
    def health_check(self):
        with self.client.get("/health", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
                _record_time(r.elapsed.total_seconds())
            else:
                r.failure(f"{r.status_code}")
                _record_error("/health", r.status_code)

    @task(15)
    def version_check(self):
        with self.client.get("/version", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(10)
    def root_endpoint(self):
        with self.client.get("/", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(10)
    def api_version(self):
        with self.client.get("/api/v1/version", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(5)
    def ai_provider_health(self):
        with self.client.get("/api/v1/rico/health/ai-provider", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(5)
    def subscription_plans(self):
        with self.client.get("/api/v1/subscription/plans", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    # --- public chat ---

    @task(8)
    def public_chat(self):
        messages = [
            "Find me software engineering jobs in Dubai",
            "What jobs match my CV?",
            "How does Rico work?",
            "Tell me about UAE job market",
            "Can you help with my CV?",
            "What is the pricing?",
            "How do I get started?",
            "Show me HSE manager jobs",
        ]
        payload = {
            "message": random.choice(messages),
            "session_id": self.session_id,
            "operation_id": _op_id(),
            "language": random.choice(["en", "ar", None]),
        }
        with self.client.post(
            "/api/v1/rico/chat/public", json=payload, catch_response=True
        ) as r:
            if r.status_code == 200:
                r.success()
                _record_time(r.elapsed.total_seconds())
            elif r.status_code == 429:
                r.failure("Rate limited")
                _record_error("chat/public", 429)
            else:
                r.failure(f"{r.status_code}")
                _record_error("chat/public", r.status_code)


class RicoAuthenticatedUser(HttpUser):
    """
    Simulates logged-in users. Performs a real login in on_start so the
    httpOnly JWT cookie is set correctly. Skips all tasks silently if
    RICO_TEST_EMAIL / RICO_TEST_PASSWORD are not configured.
    25% of simulated traffic.
    """
    wait_time = between(2, 5)
    host = HOST
    weight = 25

    def on_start(self):
        self._authenticated = False
        if not TEST_EMAIL or not TEST_PASSWORD:
            return  # skip gracefully — no test creds configured

        with self.client.post(
            "/api/v1/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            catch_response=True,
        ) as r:
            if r.status_code == 200:
                r.success()
                # The backend sets the cookie with domain=.ricohunt.com, but we're
                # hitting onrender.com directly, so requests.Session won't send it
                # automatically. Extract the token and inject it for this host.
                token = r.cookies.get("access_token")
                if token:
                    self.client.cookies.set("access_token", token)
                    self._authenticated = True
                else:
                    r.failure("Login OK but no access_token cookie in response")
            else:
                r.failure(f"Login failed: {r.status_code} — {r.text[:120]}")

    # --- guard helper ---

    def _skip_if_unauthenticated(self) -> bool:
        return not self._authenticated

    # --- tasks ---

    @task(15)
    def auth_me(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get("/api/v1/me", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            elif r.status_code == 401:
                r.failure("Session expired")
                self._authenticated = False
                _record_error("/me", 401)
            else:
                r.failure(f"{r.status_code}")

    @task(12)
    def get_profile(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get("/api/v1/rico/profile", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
                _record_time(r.elapsed.total_seconds())
            elif r.status_code == 401:
                r.failure("Unauthorized")
                self._authenticated = False
            else:
                r.failure(f"{r.status_code}")

    @task(10)
    def authenticated_chat(self):
        if self._skip_if_unauthenticated():
            return
        messages = [
            "Find matching jobs",
            "Optimize my CV for project manager roles",
            "What skills am I missing?",
            "Show my saved jobs",
            "Track my applications",
        ]
        payload = {
            "message": random.choice(messages),
            "operation_id": _op_id(),
            "language": random.choice(["en", "ar"]),
        }
        with self.client.post(
            "/api/v1/rico/chat", json=payload, catch_response=True
        ) as r:
            if r.status_code == 200:
                r.success()
                _record_time(r.elapsed.total_seconds())
            elif r.status_code == 401:
                r.failure("Unauthorized")
                self._authenticated = False
            elif r.status_code == 429:
                r.failure("AI message limit reached")
                _record_error("/rico/chat", 429)
            else:
                r.failure(f"{r.status_code}")

    @task(8)
    def list_jobs(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get("/api/v1/jobs", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(6)
    def get_job_details(self):
        if self._skip_if_unauthenticated():
            return
        job_id = random.randint(1000, 9999)
        with self.client.get(f"/api/v1/jobs/{job_id}", catch_response=True) as r:
            if r.status_code in (200, 404):
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(5)
    def get_applications(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get("/api/v1/applications", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(4)
    def get_saved_searches(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get(
            "/api/v1/rico/settings/saved-searches", catch_response=True
        ) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(3)
    def get_stats(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get("/api/v1/stats", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(3)
    def get_subscription(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get("/api/v1/subscription/me", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(2)
    def get_settings(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get("/api/v1/settings", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(2)
    def get_apply_queue(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get("/api/v1/apply/queue", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(2)
    def chat_history(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get("/api/v1/rico/chat/history", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(2)
    def application_stats(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get("/api/v1/applications/stats", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(1)
    def pipeline_status(self):
        if self._skip_if_unauthenticated():
            return
        with self.client.get("/api/v1/pipeline/status", catch_response=True) as r:
            if r.status_code in (200, 403):  # 403 = non-admin, that's fine
                r.success()
            else:
                r.failure(f"{r.status_code}")


class RicoHighLoadStress(HttpUser):
    """
    Hammers cheap endpoints to find throughput ceiling.
    Safe to run in isolation — only hits /health and /version.
    5% of simulated traffic (or run standalone for stress testing).
    """
    wait_time = between(0.5, 1.5)  # gentler than 0.1s — avoids nuking Render free tier
    host = HOST
    weight = 5

    @task(50)
    def rapid_health(self):
        self.client.get("/health")

    @task(30)
    def rapid_version(self):
        self.client.get("/version")

    @task(20)
    def rapid_api_version(self):
        self.client.get("/api/v1/version")


# ---------------------------------------------------------------------------
# Event hooks
# ---------------------------------------------------------------------------

@events.request.add_listener
def on_request(
    request_type, name, response_time, response_length,
    exception, response=None, context=None, **kwargs,
):
    global _total_requests, _total_failures
    with _lock:
        _total_requests += 1
        if exception:
            _total_failures += 1


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n" + "=" * 70)
    print("RICO HUNT LOAD TEST RESULTS")
    print("=" * 70)
    print(f"End time:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total requests:  {_total_requests:,}")
    print(f"Total failures:  {_total_failures:,}")
    if _total_requests:
        success_pct = (_total_requests - _total_failures) / _total_requests * 100
        print(f"Success rate:    {success_pct:.2f}%")

    with _lock:
        times = sorted(_response_times)

    if times:
        avg = sum(times) / len(times)
        p95 = times[int(len(times) * 0.95)]
        p99 = times[int(len(times) * 0.99)]
        print(f"\n--- Response Times (recorded tasks only) ---")
        print(f"  avg  {avg * 1000:.0f} ms")
        print(f"  min  {times[0] * 1000:.0f} ms")
        print(f"  max  {times[-1] * 1000:.0f} ms")
        print(f"  p95  {p95 * 1000:.0f} ms")
        print(f"  p99  {p99 * 1000:.0f} ms")

    with _lock:
        top_errors = sorted(_error_counts.items(), key=lambda x: -x[1])[:10]

    if top_errors:
        print("\n--- Top Errors ---")
        for key, count in top_errors:
            print(f"  {key}: {count}")

    print("=" * 70 + "\n")
