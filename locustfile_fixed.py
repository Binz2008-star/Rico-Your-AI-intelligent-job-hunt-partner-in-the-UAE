"""
Rico Hunt Load Testing - Corrected API Endpoints
Tests actual Rico API endpoints on Render
"""
from locust import HttpUser, task, between, events
import random
import time

# Global metrics
total_requests = 0
total_failures = 0
response_times = []


class RicoUser(HttpUser):
    """Simulates a typical Rico user journey with correct API endpoints"""
    wait_time = between(2, 6)
    host = "https://rico-job-automation-api.onrender.com"
    
    def on_start(self):
        """Called when a user starts"""
        self.user_id = f"test_user_{random.randint(10000, 99999)}"
        self.session_id = f"session_{self.user_id}_{random.randint(1000, 9999)}"
    
    @task(10)
    def health_check(self):
        """Health check - most frequent"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")
    
    @task(5)
    def version_check(self):
        """Version endpoint"""
        with self.client.get("/version", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                response_times.append(response.elapsed.total_seconds())
            else:
                response.failure(f"Version failed: {response.status_code}")
    
    @task(3)
    def api_version(self):
        """API v1 version"""
        with self.client.get("/api/v1/version", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"API version failed: {response.status_code}")
    
    @task(2)
    def root_endpoint(self):
        """Root endpoint"""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Root failed: {response.status_code}")
    
    @task(2)
    def public_chat(self):
        """Public chat - no auth required"""
        messages = [
            "Find me jobs in Dubai",
            "What jobs are available?",
            "Help with my CV",
            "Tell me about Rico",
            "How does job matching work?"
        ]
        
        payload = {
            "message": random.choice(messages),
            "session_id": self.session_id,
            "email": None,
            "language": "en"
        }
        
        with self.client.post("/api/v1/rico/chat/public", json=payload, 
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                response_times.append(response.elapsed.total_seconds())
            else:
                response.failure(f"Public chat failed: {response.status_code}")


class RicoHighLoadUser(HttpUser):
    """High-load stress testing"""
    wait_time = between(0.5, 1.5)
    host = "https://rico-job-automation-api.onrender.com"
    
    @task(20)
    def rapid_health_checks(self):
        """Rapid health checks"""
        self.client.get("/health")
    
    @task(10)
    def rapid_version_checks(self):
        """Rapid version checks"""
        self.client.get("/version")


# Custom events
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    global total_requests
    total_requests += 1
    if exception:
        global total_failures
        total_failures += 1


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary when test stops"""
    print(f"\n{'='*60}")
    print(f"Total Requests: {total_requests}")
    print(f"Total Failures: {total_failures}")
    if total_requests > 0:
        print(f"Failure Rate: {total_failures/total_requests*100:.2f}%")
    if response_times:
        print(f"Avg Response Time: {sum(response_times)/len(response_times)*1000:.2f}ms")
        print(f"Max Response Time: {max(response_times)*1000:.2f}ms")
    print(f"{'='*60}\n")


# Test configurations:
# 1. Normal load: locust -f locustfile_fixed.py -u 50 -r 5 --run-time 5m --headless
# 2. High load: locust -f locustfile_fixed.py -u 100 -r 10 --run-time 5m --headless
# 3. Stress test: locust -f locustfile_fixed.py RicoHighLoadUser -u 200 -r 20 --run-time 10m --headless
