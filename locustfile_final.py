"""
Rico Hunt Production Load Testing - FIXED VERSION
Real auth, thread-safe metrics, realistic stress levels
"""
from locust import HttpUser, task, between, events
import random
import time
import threading
import uuid
from datetime import datetime

# Thread-safe metrics using locks
_metrics_lock = threading.Lock()
total_requests = 0
total_failures = 0
response_times = []
error_counts = {}
auth_success_count = 0
auth_failure_count = 0


def safe_increment_request():
    """Thread-safe request counter"""
    global total_requests
    with _metrics_lock:
        total_requests += 1


def safe_increment_failure():
    """Thread-safe failure counter"""
    global total_failures
    with _metrics_lock:
        total_failures += 1


def safe_track_response_time(response_time):
    """Thread-safe response time tracking"""
    with _metrics_lock:
        response_times.append(response_time)


def safe_track_error(endpoint, status_code):
    """Thread-safe error tracking"""
    with _metrics_lock:
        key = f"{endpoint}:{status_code}"
        error_counts[key] = error_counts.get(key, 0) + 1


def _operation_id() -> str:
    """Generate valid operation_id (min 8 chars, max 80)"""
    return uuid.uuid4().hex[:16]  # Always 16 characters


def safe_track_auth(success=True):
    """Track auth success/failure"""
    global auth_success_count, auth_failure_count
    with _metrics_lock:
        if success:
            auth_success_count += 1
        else:
            auth_failure_count += 1


def get_response_time(response):
    """Safely extract response time"""
    try:
        if hasattr(response, 'elapsed'):
            return response.elapsed.total_seconds()
    except:
        pass
    return None


class RicoPublicUser(HttpUser):
    """
    PUBLIC users (no auth required)
    70% of traffic
    """
    wait_time = between(3, 8)
    host = "https://rico-job-automation-api.onrender.com"
    weight = 70

    def on_start(self):
        self.session_id = f"pub_{random.randint(100000, 999999)}"
        self.email = None

    def track_metrics(self, response, endpoint_name):
        """Track all metrics for any response"""
        safe_increment_request()
        if response.status_code >= 400:
            safe_increment_failure()
            safe_track_error(endpoint_name, response.status_code)
        resp_time = get_response_time(response)
        if resp_time:
            safe_track_response_time(resp_time)

    @task(20)
    def health_check(self):
        with self.client.get("/health", catch_response=True) as response:
            self.track_metrics(response, "/health")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health: {response.status_code}")

    @task(15)
    def version_check(self):
        with self.client.get("/version", catch_response=True) as response:
            self.track_metrics(response, "/version")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Version: {response.status_code}")

    @task(10)
    def root_endpoint(self):
        with self.client.get("/", catch_response=True) as response:
            self.track_metrics(response, "/")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Root: {response.status_code}")

    @task(10)
    def api_version(self):
        with self.client.get("/api/v1/version", catch_response=True) as response:
            self.track_metrics(response, "/api/v1/version")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"API version: {response.status_code}")

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
            "Show me HSE manager jobs"
        ]

        payload = {
            "message": random.choice(messages),
            "session_id": self.session_id,
            "email": None,
            "operation_id": _operation_id(),
            "language": random.choice(["en", "ar"])
        }

        with self.client.post("/api/v1/rico/chat/public", json=payload,
                            catch_response=True) as response:
            self.track_metrics(response, "/rico/chat/public")
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Public chat: {response.status_code}")

    @task(5)
    def ai_provider_health(self):
        with self.client.get("/api/v1/rico/health/ai-provider",
                            catch_response=True) as response:
            self.track_metrics(response, "/rico/health/ai-provider")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"AI health: {response.status_code}")

    @task(5)
    def subscription_plans(self):
        with self.client.get("/api/v1/subscription/plans",
                            catch_response=True) as response:
            self.track_metrics(response, "/subscription/plans")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Plans: {response.status_code}")

    @task(3)
    def docs_endpoint(self):
        """API docs - for developers"""
        with self.client.get("/api/docs", catch_response=True) as response:
            self.track_metrics(response, "/api/docs")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Docs: {response.status_code}")


class RicoAuthenticatedUser(HttpUser):
    """
    AUTHENTICATED users with REAL login
    25% of traffic
    """
    wait_time = between(2, 5)
    host = "https://rico-job-automation-api.onrender.com"
    weight = 25

    # Real test credentials
    TEST_EMAIL = "robenedwan@gmail.com"
    TEST_PASSWORD = "binz@2008"

    def on_start(self):
        """Real login to get JWT cookie"""
        self.session_id = f"auth_{random.randint(100000, 999999)}"
        self.is_authenticated = False

        # Try to register first (if user doesn't exist)
        register_payload = {
            "email": self.TEST_EMAIL,
            "password": self.TEST_PASSWORD,
            "name": "Load Test User"
        }

        # Attempt registration (ignoring if already exists)
        try:
            self.client.post("/api/v1/auth/register", json=register_payload,
                           catch_response=True, timeout=5)
        except:
            pass  # User might already exist

        # Real login
        login_payload = {
            "email": self.TEST_EMAIL,
            "password": self.TEST_PASSWORD
        }

        try:
            with self.client.post("/api/v1/auth/login", json=login_payload,
                                catch_response=True, timeout=10) as response:
                safe_track_auth(response.status_code == 200)
                if response.status_code == 200:
                    self.is_authenticated = True
                    # FIX: Manually extract and inject cookie (domain mismatch fix)
                    token = response.cookies.get("access_token")
                    if token:
                        self.client.cookies.set("access_token", token)
                else:
                    # Try with different test user
                    self.try_alternative_login()
        except Exception as e:
            safe_track_auth(False)
            print(f"Login failed: {e}")

    def try_alternative_login(self):
        """Try with alternative test credentials"""
        alt_email = f"test_user_{random.randint(1000, 9999)}@ricohunt.com"

        # Register new user
        register_payload = {
            "email": alt_email,
            "password": self.TEST_PASSWORD,
            "name": f"Test User {random.randint(1000, 9999)}"
        }

        try:
            self.client.post("/api/v1/auth/register", json=register_payload,
                           catch_response=True, timeout=5)
        except:
            pass

        # Login with new user
        login_payload = {
            "email": alt_email,
            "password": self.TEST_PASSWORD
        }

        try:
            with self.client.post("/api/v1/auth/login", json=login_payload,
                                catch_response=True, timeout=10) as response:
                safe_track_auth(response.status_code == 200)
                if response.status_code == 200:
                    self.is_authenticated = True
                    self.TEST_EMAIL = alt_email
                    # FIX: Manually extract and inject cookie
                    token = response.cookies.get("access_token")
                    if token:
                        self.client.cookies.set("access_token", token)
        except:
            safe_track_auth(False)

    def track_metrics(self, response, endpoint_name):
        """Track all metrics"""
        safe_increment_request()
        if response.status_code >= 400:
            safe_increment_failure()
            safe_track_error(endpoint_name, response.status_code)
        resp_time = get_response_time(response)
        if resp_time:
            safe_track_response_time(resp_time)

    def check_auth(self):
        """Skip if not authenticated"""
        if not self.is_authenticated:
            return False
        return True

    @task(15)
    def auth_me(self):
        if not self.check_auth():
            return

        with self.client.get("/api/v1/me", catch_response=True) as response:
            self.track_metrics(response, "/me")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Auth me: {response.status_code}")

    @task(12)
    def get_profile(self):
        if not self.check_auth():
            return

        with self.client.get("/api/v1/rico/profile", catch_response=True) as response:
            self.track_metrics(response, "/rico/profile")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Profile: {response.status_code}")

    @task(10)
    def authenticated_chat(self):
        if not self.check_auth():
            return

        messages = [
            "Find matching jobs",
            "Optimize my CV",
            "What skills am I missing?",
            "Show my saved jobs",
            "Track my applications"
        ]

        payload = {
            "message": random.choice(messages),
            "operation_id": _operation_id(),
            "language": random.choice(["en", "ar"])
        }

        with self.client.post("/api/v1/rico/chat", json=payload,
                            catch_response=True) as response:
            self.track_metrics(response, "/rico/chat")
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                response.failure("Unauthorized - session expired")
                self.is_authenticated = False
            elif response.status_code == 429:
                response.failure("AI message limit reached")
            else:
                response.failure(f"Auth chat: {response.status_code}")

    @task(8)
    def list_jobs(self):
        if not self.check_auth():
            return

        with self.client.get("/api/v1/jobs", catch_response=True) as response:
            self.track_metrics(response, "/jobs")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Jobs list: {response.status_code}")

    @task(6)
    def get_job_details(self):
        if not self.check_auth():
            return

        job_id = random.randint(1000, 9999)
        with self.client.get(f"/api/v1/jobs/{job_id}",
                          catch_response=True) as response:
            self.track_metrics(response, f"/jobs/{job_id}")
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.success()  # Job not found is OK
            else:
                response.failure(f"Job details: {response.status_code}")

    @task(5)
    def get_applications(self):
        if not self.check_auth():
            return

        with self.client.get("/api/v1/applications",
                            catch_response=True) as response:
            self.track_metrics(response, "/applications")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Applications: {response.status_code}")

    @task(4)
    def get_saved_searches(self):
        if not self.check_auth():
            return

        with self.client.get("/api/v1/rico/settings/saved-searches",
                            catch_response=True) as response:
            self.track_metrics(response, "/rico/settings/saved-searches")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Saved searches: {response.status_code}")

    @task(3)
    def get_stats(self):
        if not self.check_auth():
            return

        with self.client.get("/api/v1/stats", catch_response=True) as response:
            self.track_metrics(response, "/stats")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Stats: {response.status_code}")

    @task(3)
    def get_subscription(self):
        if not self.check_auth():
            return

        with self.client.get("/api/v1/subscription/me",
                            catch_response=True) as response:
            self.track_metrics(response, "/subscription/me")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Subscription: {response.status_code}")

    @task(2)
    def get_settings(self):
        if not self.check_auth():
            return

        with self.client.get("/api/v1/settings", catch_response=True) as response:
            self.track_metrics(response, "/settings")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Settings: {response.status_code}")

    @task(2)
    def get_apply_queue(self):
        if not self.check_auth():
            return

        with self.client.get("/api/v1/apply/queue",
                            catch_response=True) as response:
            self.track_metrics(response, "/apply/queue")
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Apply queue: {response.status_code}")


class RicoModerateStress(HttpUser):
    """
    MODERATE stress testing - safe for Render free tier
    5% of traffic
    """
    wait_time = between(0.5, 1.0)  # Less aggressive than 0.1s
    host = "https://rico-job-automation-api.onrender.com"
    weight = 5

    @task(40)
    def moderate_health(self):
        """Moderate health checks"""
        with self.client.get("/health", catch_response=True) as response:
            safe_increment_request()
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health stress: {response.status_code}")
            resp_time = get_response_time(response)
            if resp_time:
                safe_track_response_time(resp_time)

    @task(30)
    def moderate_version(self):
        """Moderate version checks"""
        with self.client.get("/version", catch_response=True) as response:
            safe_increment_request()
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Version stress: {response.status_code}")

    @task(20)
    def moderate_api_version(self):
        """Moderate API version"""
        with self.client.get("/api/v1/version", catch_response=True) as response:
            safe_increment_request()
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"API version stress: {response.status_code}")

    @task(10)
    def moderate_public_chat(self):
        """Moderate public chat"""
        payload = {
            "message": "Quick test message",
            "session_id": f"stress_{random.randint(1000, 9999)}",
            "email": None
        }

        with self.client.post("/api/v1/rico/chat/public", json=payload,
                            catch_response=True) as response:
            safe_increment_request()
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Public chat stress: {response.status_code}")
            resp_time = get_response_time(response)
            if resp_time:
                safe_track_response_time(resp_time)


# Event listeners
@events.request.add_listener
def on_request(request_type, name, response_time, response_length,
               exception, response=None, context=None, **kwargs):
    if exception:
        safe_increment_failure()


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Comprehensive summary report"""
    print("\n" + "="*75)
    print("RICO HUNT LOAD TEST - FINAL REPORT")
    print("="*75)
    print(f"Test End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with _metrics_lock:
        print(f"\n--- Overall Statistics ---")
        print(f"Total Requests:     {total_requests:,}")
        print(f"Total Failures:     {total_failures:,}")
        print(f"Auth Success:       {auth_success_count}")
        print(f"Auth Failures:      {auth_failure_count}")

        if total_requests > 0:
            success_rate = ((total_requests - total_failures) / total_requests) * 100
            print(f"Success Rate:       {success_rate:.2f}%")
            print(f"Failure Rate:       {(total_failures/total_requests)*100:.2f}%")

        print(f"\n--- Response Times ---")
        if response_times:
            sorted_times = sorted(response_times)
            count = len(sorted_times)

            print(f"Count:              {count:,}")
            print(f"Average:            {sum(sorted_times)/count*1000:.2f} ms")
            print(f"Min:                {min(sorted_times)*1000:.2f} ms")
            print(f"Max:                {max(sorted_times)*1000:.2f} ms")

            # Percentiles
            p50 = sorted_times[int(count * 0.50)]
            p95 = sorted_times[int(count * 0.95)]
            p99 = sorted_times[int(count * 0.99)]

            print(f"P50 (Median):       {p50*1000:.2f} ms")
            print(f"P95:                {p95*1000:.2f} ms")
            print(f"P99:                {p99*1000:.2f} ms")
        else:
            print("No response times recorded")

        print(f"\n--- Top Errors ---")
        if error_counts:
            sorted_errors = sorted(error_counts.items(), key=lambda x: -x[1])[:10]
            for error, count in sorted_errors:
                print(f"  {error}: {count}")
        else:
            print("  No errors recorded")

    print("="*75 + "\n")


# Test Configurations:
#
# 1. LIGHT TEST (2 min, 20 users):
#    locust -f locustfile_final.py -u 20 -r 5 --run-time 2m --headless
#
# 2. NORMAL LOAD (10 min, 100 users):
#    locust -f locustfile_final.py -u 100 -r 10 --run-time 10m --headless
#
# 3. HIGH LOAD (15 min, 300 users):
#    locust -f locustfile_final.py -u 300 -r 30 --run-time 15m --headless
#
# 4. MODERATE STRESS (10 min, 500 users, moderate pace):
#    locust -f locustfile_final.py RicoModerateStress -u 500 -r 50 --run-time 10m --headless
#
# 5. WEB UI:
#    locust -f locustfile_final.py --web-host=0.0.0.0 --web-port=8089
#
# IMPORTANT: Replace TEST_EMAIL and TEST_PASSWORD with real test account credentials
# or the auth tests will fail with 401
