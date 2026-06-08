"""
Rico Hunt - PUBLIC ENDPOINTS ONLY Load Test
No authentication required - safe for production testing
"""
from locust import HttpUser, task, between, events
import random
import threading
import uuid
from datetime import datetime

# Thread-safe metrics
_metrics_lock = threading.Lock()
total_requests = 0
total_failures = 0
response_times = []


def safe_increment_request():
    with _metrics_lock:
        global total_requests
        total_requests += 1


def safe_increment_failure():
    with _metrics_lock:
        global total_failures
        total_failures += 1


def safe_track_response_time(resp_time):
    with _metrics_lock:
        response_times.append(resp_time)


def _operation_id():
    return uuid.uuid4().hex[:16]


class RicoPublicOnly(HttpUser):
    """
    PUBLIC endpoints only - no auth required
    Safe for production load testing
    """
    wait_time = between(2, 5)
    host = "https://rico-job-automation-api.onrender.com"
    
    def on_start(self):
        self.session_id = f"load_{uuid.uuid4().hex[:12]}"
    
    def track_metrics(self, response):
        safe_increment_request()
        if response.status_code >= 400:
            safe_increment_failure()
        if hasattr(response, 'elapsed'):
            safe_track_response_time(response.elapsed.total_seconds())
    
    @task(20)
    def health_check(self):
        with self.client.get("/health", catch_response=True) as response:
            self.track_metrics(response)
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health: {response.status_code}")
    
    @task(15)
    def version_check(self):
        with self.client.get("/version", catch_response=True) as response:
            self.track_metrics(response)
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Version: {response.status_code}")
    
    @task(10)
    def api_version(self):
        with self.client.get("/api/v1/version", catch_response=True) as response:
            self.track_metrics(response)
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"API version: {response.status_code}")
    
    @task(8)
    def root_endpoint(self):
        with self.client.get("/", catch_response=True) as response:
            self.track_metrics(response)
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Root: {response.status_code}")
    
    @task(8)
    def public_chat(self):
        messages = [
            "Find software jobs in Dubai",
            "What jobs match my CV?",
            "How does Rico work?",
            "Tell me about UAE market",
            "Help with CV",
            "What is pricing?",
            "Get started",
            "HSE manager jobs"
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
            self.track_metrics(response)
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limited (expected)")
            else:
                response.failure(f"Public chat: {response.status_code}")
    
    @task(5)
    def ai_provider_health(self):
        with self.client.get("/api/v1/rico/health/ai-provider",
                            catch_response=True) as response:
            self.track_metrics(response)
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"AI health: {response.status_code}")
    
    @task(5)
    def subscription_plans(self):
        with self.client.get("/api/v1/subscription/plans",
                            catch_response=True) as response:
            self.track_metrics(response)
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Plans: {response.status_code}")
    
    @task(3)
    def docs_endpoint(self):
        with self.client.get("/api/docs", catch_response=True) as response:
            self.track_metrics(response)
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Docs: {response.status_code}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    with _metrics_lock:
        print("\n" + "="*70)
        print("RICO HUNT - PUBLIC ENDPOINTS LOAD TEST")
        print("="*70)
        print(f"Test End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Requests: {total_requests:,}")
        print(f"Failures: {total_failures:,}")
        if total_requests > 0:
            print(f"Success Rate: {((total_requests-total_failures)/total_requests)*100:.1f}%")
        if response_times:
            sorted_times = sorted(response_times)
            print(f"\nResponse Times:")
            print(f"  Avg: {sum(sorted_times)/len(sorted_times)*1000:.0f} ms")
            print(f"  Min: {min(sorted_times)*1000:.0f} ms")
            print(f"  Max: {max(sorted_times)*1000:.0f} ms")
            print(f"  P95: {sorted_times[int(len(sorted_times)*0.95)]*1000:.0f} ms")
        print("="*70 + "\n")


# Test Commands:
# Light:   locust -f locustfile_public_only.py -u 20 -r 5 --run-time 2m --headless
# Normal:  locust -f locustfile_public_only.py -u 100 -r 10 --run-time 5m --headless
# High:    locust -f locustfile_public_only.py -u 300 -r 30 --run-time 10m --headless
# Web UI:  locust -f locustfile_public_only.py --web-host=0.0.0.0 --web-port=8089
