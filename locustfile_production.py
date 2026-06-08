"""
Rico Hunt Production Load Testing - Real API Endpoints
Tests actual Rico API endpoints with realistic traffic patterns
"""
from locust import HttpUser, task, between, events
import random
import time
import uuid
from datetime import datetime


def _operation_id() -> str:
    """Generate valid operation_id (min 8 chars, max 80)"""
    return uuid.uuid4().hex[:16]  # Always 16 characters

# Global metrics
total_requests = 0
total_failures = 0
response_times = []
error_counts = {}


class RicoPublicUser(HttpUser):
    """
    Simulates PUBLIC users (no JWT required)
    Landing page visitors, potential signups
    """
    wait_time = between(3, 8)
    host = "https://rico-job-automation-api.onrender.com"
    weight = 70  # 70% of traffic is public

    def on_start(self):
        self.session_id = f"public_{random.randint(100000, 999999)}"
        self.email = None

    @task(20)
    def health_check(self):
        """Health check - most frequent for monitoring"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                track_response_time(response)
            else:
                response.failure(f"Health check: {response.status_code}")
                track_error("/health", response.status_code)

    @task(15)
    def version_check(self):
        """Version endpoint"""
        with self.client.get("/version", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Version: {response.status_code}")

    @task(10)
    def root_endpoint(self):
        """Root ping"""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Root: {response.status_code}")

    @task(10)
    def api_version(self):
        """API v1 version"""
        with self.client.get("/api/v1/version", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"API version: {response.status_code}")

    @task(8)
    def public_chat(self):
        """Public chat - landing page visitors"""
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
            "email": self.email,
            "operation_id": _operation_id(),
            "language": random.choice(["en", "ar"])
        }

        with self.client.post("/api/v1/rico/chat/public", json=payload,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                track_response_time(response)
            elif response.status_code == 429:
                response.failure("Rate limited")
                track_error("chat/public", 429)
            else:
                response.failure(f"Public chat: {response.status_code}")
                track_error("chat/public", response.status_code)

    @task(5)
    def ai_provider_health(self):
        """Check AI provider status"""
        with self.client.get("/api/v1/rico/health/ai-provider",
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"AI health: {response.status_code}")

    @task(5)
    def subscription_plans(self):
        """View pricing plans"""
        with self.client.get("/api/v1/subscription/plans",
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Plans: {response.status_code}")

    @task(3)
    def simulate_onboarding_start(self):
        """Simulate starting onboarding (via Jotform webhook simulation)"""
        # Note: Actual Jotform webhook requires secret
        pass  # Skip for safety


class RicoAuthenticatedUser(HttpUser):
    """
    Simulates AUTHENTICATED users (JWT required)
    Active users with accounts
    """
    wait_time = between(2, 5)
    host = "https://rico-job-automation-api.onrender.com"
    weight = 25  # 25% of traffic is authenticated

    def on_start(self):
        self.user_id = f"user_{random.randint(10000, 99999)}@test.com"
        self.session_id = f"auth_{random.randint(100000, 999999)}"
        # Simulate JWT auth (in real test, you'd login first)
        self.cookies = {"access_token": f"mock_jwt_{random.randint(1000, 9999)}"}

    @task(15)
    def auth_me(self):
        """Get current user info"""
        with self.client.get("/api/v1/me", cookies=self.cookies,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                response.failure("Unauthorized - session expired")
                track_error("/me", 401)
            else:
                response.failure(f"Auth me: {response.status_code}")

    @task(12)
    def get_profile(self):
        """Get Rico profile"""
        with self.client.get("/api/v1/rico/profile", cookies=self.cookies,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                response.failure("Unauthorized")
            else:
                response.failure(f"Profile: {response.status_code}")

    @task(10)
    def authenticated_chat(self):
        """Authenticated chat with full features"""
        messages = [
            "Find matching jobs",
            "Optimize my CV for project manager roles",
            "What skills am I missing?",
            "Show my saved jobs",
            "Track my applications"
        ]

        payload = {
            "message": random.choice(messages),
            "operation_id": f"op_{random.randint(1000, 9999)}",
            "language": random.choice(["en", "ar"])
        }

        with self.client.post("/api/v1/rico/chat", json=payload,
                            cookies=self.cookies, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                track_response_time(response)
            elif response.status_code == 401:
                response.failure("Unauthorized")
            elif response.status_code == 429:
                response.failure("AI message limit reached")
                track_error("/rico/chat", 429)
            else:
                response.failure(f"Auth chat: {response.status_code}")

    @task(8)
    def list_jobs(self):
        """Get job listings"""
        with self.client.get("/api/v1/jobs", cookies=self.cookies,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Jobs list: {response.status_code}")

    @task(6)
    def get_job_details(self):
        """Get specific job details"""
        job_id = random.randint(1000, 9999)
        with self.client.get(f"/api/v1/jobs/{job_id}", cookies=self.cookies,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.success()  # Job not found is OK
            else:
                response.failure(f"Job details: {response.status_code}")

    @task(5)
    def get_applications(self):
        """Get user's applications"""
        with self.client.get("/api/v1/applications", cookies=self.cookies,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Applications: {response.status_code}")

    @task(4)
    def get_saved_searches(self):
        """List saved searches"""
        with self.client.get("/api/v1/rico/settings/saved-searches",
                            cookies=self.cookies, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Saved searches: {response.status_code}")

    @task(3)
    def get_stats(self):
        """Get dashboard stats"""
        with self.client.get("/api/v1/stats", cookies=self.cookies,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Stats: {response.status_code}")

    @task(3)
    def get_subscription(self):
        """Get subscription info"""
        with self.client.get("/api/v1/subscription/me", cookies=self.cookies,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Subscription: {response.status_code}")

    @task(2)
    def get_settings(self):
        """Get user settings"""
        with self.client.get("/api/v1/settings", cookies=self.cookies,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Settings: {response.status_code}")

    @task(2)
    def get_apply_queue(self):
        """Get apply queue"""
        with self.client.get("/api/v1/apply/queue", cookies=self.cookies,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Apply queue: {response.status_code}")


class RicoPublicBaselineUser(HttpUser):
    """
    BASELINE mode: Low frequency chat to avoid 429s
    Target: 98-100% success rate
    Realistic wait_time between chat messages
    """
    wait_time = between(5, 15)  # Longer wait to stay under rate limits
    host = "https://rico-job-automation-api.onrender.com"

    def on_start(self):
        self.session_id = f"baseline_{random.randint(100000, 999999)}"
        self.email = None

    @task(25)
    def health_check(self):
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health: {response.status_code}")

    @task(20)
    def version_check(self):
        with self.client.get("/version", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Version: {response.status_code}")

    @task(15)
    def api_version(self):
        with self.client.get("/api/v1/version", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"API version: {response.status_code}")

    @task(10)
    def root_endpoint(self):
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Root: {response.status_code}")

    @task(2)  # LOW frequency chat to avoid rate limits
    def public_chat_baseline(self):
        """Chat with realistic spacing - expect 0% 429s"""
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
            "email": self.email,
            "operation_id": _operation_id(),
            "language": random.choice(["en", "ar"])
        }

        with self.client.post("/api/v1/rico/chat/public", json=payload,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                # 429 is a FAILURE in baseline mode (should not happen with proper spacing)
                response.failure(f"Unexpected 429 in baseline mode")
            else:
                response.failure(f"Chat: {response.status_code}")

    @task(8)
    def ai_provider_health(self):
        with self.client.get("/api/v1/rico/health/ai-provider",
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"AI health: {response.status_code}")

    @task(8)
    def subscription_plans(self):
        with self.client.get("/api/v1/subscription/plans",
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Plans: {response.status_code}")


class RicoPublicRateLimitUser(HttpUser):
    """
    RATE LIMIT mode: Intentionally hit chat harder
    Purpose: Test rate limiter behavior and threshold
    429 is EXPECTED and counted as protected (not app failure)
    """
    wait_time = between(1, 3)  # Faster requests to trigger rate limits
    host = "https://rico-job-automation-api.onrender.com"

    def on_start(self):
        self.session_id = f"ratelimit_{random.randint(100000, 999999)}"
        self.email = None
        self.chat_requests = 0
        self.rate_limited_count = 0

    @task(10)
    def health_check(self):
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health: {response.status_code}")

    @task(8)
    def version_check(self):
        with self.client.get("/version", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Version: {response.status_code}")

    @task(25)  # HIGH frequency chat to trigger rate limits
    def public_chat_rate_limit_test(self):
        """Intentionally aggressive chat to test rate limiter"""
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
            "email": self.email,
            "operation_id": _operation_id(),
            "language": random.choice(["en", "ar"])
        }

        self.chat_requests += 1

        with self.client.post("/api/v1/rico/chat/public", json=payload,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                # 429 is EXPECTED in rate limit test - rate limiter working
                self.rate_limited_count += 1
                response.success()  # Count as success (protected by rate limiter)
            else:
                response.failure(f"Unexpected error: {response.status_code}")


class RicoHighLoadStress(HttpUser):
    """
    High-load stress testing
    Rapid requests to test API limits
    """
    wait_time = between(0.1, 0.5)
    host = "https://rico-job-automation-api.onrender.com"
    weight = 5  # 5% of traffic is high-load stress

    @task(50)
    def rapid_health(self):
        """Very rapid health checks"""
        self.client.get("/health")

    @task(30)
    def rapid_version(self):
        """Rapid version checks"""
        self.client.get("/version")

    @task(20)
    def rapid_api_version(self):
        """Rapid API version"""
        self.client.get("/api/v1/version")


# Helper functions
def track_response_time(response):
    """Track response times for metrics"""
    try:
        if hasattr(response, 'elapsed'):
            response_times.append(response.elapsed.total_seconds())
    except:
        pass


def track_error(endpoint, status_code):
    """Track error counts"""
    key = f"{endpoint}:{status_code}"
    error_counts[key] = error_counts.get(key, 0) + 1


# Event listeners
@events.request.add_listener
def on_request(request_type, name, response_time, response_length,
               exception, response=None, context=None, **kwargs):
    global total_requests
    total_requests += 1
    if exception:
        global total_failures
        total_failures += 1


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print comprehensive summary when test stops"""
    print("\n" + "="*70)
    print("RICO HUNT LOAD TEST RESULTS")
    print("="*70)
    print(f"Test End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Requests: {total_requests:,}")
    print(f"Total Failures: {total_failures:,}")
    if total_requests > 0:
        print(f"Failure Rate: {(total_failures/total_requests)*100:.2f}%")
        print(f"Success Rate: {((total_requests-total_failures)/total_requests)*100:.2f}%")

    if response_times:
        avg_time = sum(response_times) / len(response_times)
        sorted_times = sorted(response_times)
        p95_idx = int(len(sorted_times) * 0.95)
        p99_idx = int(len(sorted_times) * 0.99)

        print(f"\n--- Response Times ---")
        print(f"Average:     {avg_time*1000:.2f} ms")
        print(f"Min:         {min(response_times)*1000:.2f} ms")
        print(f"Max:         {max(response_times)*1000:.2f} ms")
        print(f"P95:         {sorted_times[min(p95_idx, len(sorted_times)-1)]*1000:.2f} ms")
        print(f"P99:         {sorted_times[min(p99_idx, len(sorted_times)-1)]*1000:.2f} ms")

    if error_counts:
        print(f"\n--- Error Summary ---")
        for error, count in sorted(error_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {error}: {count}")

    print("="*70 + "\n")


# Test Configurations:
#
# === BASELINE MODE (98-100% success, no 429s expected) ===
# Low chat frequency, realistic wait times
# 1. Light baseline:
#    locust -f locustfile_production.py RicoPublicBaselineUser -u 20 -r 5 --run-time 2m --headless
# 2. Normal baseline:
#    locust -f locustfile_production.py RicoPublicBaselineUser -u 100 -r 10 --run-time 10m --headless
#
# === RATE LIMIT MODE (Test rate limiter behavior) ===
# High chat frequency, expect 429s (rate limiter protection)
# 3. Rate limit test:
#    locust -f locustfile_production.py RicoPublicRateLimitUser -u 20 -r 5 --run-time 2m --headless
#
# === ORIGINAL MIXED MODE ===
# 4. Light:    locust -f locustfile_production.py -u 20 -r 5 --run-time 2m --headless
# 5. Normal:   locust -f locustfile_production.py -u 100 -r 10 --run-time 10m --headless
# 6. High:     locust -f locustfile_production.py -u 300 -r 30 --run-time 15m --headless
# 7. Stress:   locust -f locustfile_production.py RicoHighLoadStress -u 500 -r 50 --run-time 10m --headless
#
# === WEB UI ===
#    locust -f locustfile_production.py --web-host=0.0.0.0 --web-port=8089
#
# === DISTRIBUTED TESTING ===
#    Master: locust -f locustfile_production.py --master
#    Worker: locust -f locustfile_production.py --worker --master-host=<master-ip>
