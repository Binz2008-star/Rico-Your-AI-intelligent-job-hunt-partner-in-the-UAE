"""
Rico Hunt Load Testing - Improved Locust Performance Test
Tests API endpoints under simulated user load with realistic scenarios
"""
from locust import HttpUser, task, between, events
import random
import json
import time
from locust.runners import MasterRunner, WorkerRunner

# Global metrics
total_requests = 0
total_failures = 0
response_times = []


class RicoUser(HttpUser):
    """Simulates a typical Rico user journey"""
    wait_time = between(2, 6)  # More realistic wait time
    host = "https://rico-job-automation-api.onrender.com"

    # Authentication (if your API needs it)
    # Replace with your actual auth method
    auth_header = {
        "Authorization": "Bearer YOUR_API_KEY_HERE",
        "Content-Type": "application/json"
    }

    def on_start(self):
        """Called when a user starts - simulate login/onboarding"""
        self.user_id = f"test_user_{random.randint(10000, 99999)}"
        self.session_id = f"session_{self.user_id}_{random.randint(1000, 9999)}"

        # Simulate user login or profile creation
        try:
            self.client.post("/api/auth/login", json={
                "user_id": self.user_id,
                "email": f"{self.user_id}@test.com"
            }, headers=self.auth_header, catch_response=True)
        except:
            pass  # Auth might not be needed for testing

    @task(10)
    def health_check(self):
        """Health check - most frequent (40% of traffic)"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(5)
    def get_jobs_with_filters(self):
        """Realistic job search with filters (25% of traffic)"""
        params = {
            "limit": random.choice([5, 10, 20]),
            "location": random.choice(["Dubai", "Abu Dhabi", "Sharjah", "Ajman"]),
            "role": random.choice(["Software Engineer", "Project Manager", "HSE Manager", "Operations"]),
        }

        with self.client.get("/api/jobs", params=params,
                           headers=self.auth_header, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                # Track response time
                response_times.append(response.elapsed.total_seconds())
            else:
                response.failure(f"Job search failed: {response.status_code}")

    @task(3)
    def chat_interaction_realistic(self):
        """Realistic chat interaction (15% of traffic)"""
        messages = [
            "Find me software engineering jobs in Dubai",
            "What jobs match my CV?",
            "Show me project manager jobs with salary above 15k",
            "Help me optimize my CV",
            "What skills should I learn to get hired faster?"
        ]

        payload = {
            "message": random.choice(messages),
            "user_id": self.user_id,
            "session_id": self.session_id,
            "cv_id": f"cv_{self.user_id}"
        }

        with self.client.post("/api/chat", json=payload,
                            headers=self.auth_header, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                response_times.append(response.elapsed.total_seconds())
            else:
                response.failure(f"Chat failed: {response.status_code}")

    @task(2)
    def upload_cv_simulation(self):
        """Simulate CV upload (10% of traffic)"""
        # In real scenario, this would upload a file
        payload = {
            "user_id": self.user_id,
            "cv_text": "Software Engineer with 5 years experience in SaaS, AI, and backend development",
            "skills": ["JavaScript", "TypeScript", "Python", "Redis", "Tailwind CSS"],
            "experience_years": random.randint(2, 10),
            "target_role": random.choice(["Software Engineer", "Technical Project Manager", "SaaS Developer"])
        }

        with self.client.post("/api/cv/upload", json=payload,
                            headers=self.auth_header, catch_response=True) as response:
            if response.status_code in [200, 201]:
                response.success()
            else:
                response.failure(f"CV upload failed: {response.status_code}")

    @task(2)
    def get_match_scores(self):
        """Get job match scores (7% of traffic)"""
        job_id = random.randint(1000, 9999)

        with self.client.get(f"/api/match/{job_id}",
                           headers=self.auth_header, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                response_times.append(response.elapsed.total_seconds())
            else:
                response.failure(f"Match score failed: {response.status_code}")

    @task(1)
    def submit_application(self):
        """Submit job application (3% of traffic)"""
        job_id = random.randint(1000, 9999)

        payload = {
            "user_id": self.user_id,
            "job_id": job_id,
            "cover_letter": f"Interested in this position as {self.user_id}",
            "cv_id": f"cv_{self.user_id}"
        }

        with self.client.post("/api/applications/submit", json=payload,
                            headers=self.auth_header, catch_response=True) as response:
            if response.status_code in [200, 201]:
                response.success()
            else:
                response.failure(f"Application failed: {response.status_code}")

    @task(1)
    def get_applications_history(self):
        """Get application history (5% of traffic)"""
        with self.client.get(f"/api/applications?user_id={self.user_id}&limit=10",
                           headers=self.auth_header, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Applications history failed: {response.status_code}")


class RicoHighLoadUser(HttpUser):
    """Simulates high-load scenario with rapid API calls"""
    wait_time = between(0.5, 1.5)  # Faster but not unrealistic
    host = "https://rico-job-automation-api.onrender.com"

    auth_header = {
        "Authorization": "Bearer YOUR_API_KEY_HERE",
        "Content-Type": "application/json"
    }

    @task(20)
    def rapid_health_checks(self):
        """Rapid health checks - stress test"""
        self.client.get("/health", headers=self.auth_header)

    @task(10)
    def rapid_job_searches(self):
        """Rapid job searches"""
        self.client.get("/api/jobs?limit=5", headers=self.auth_header)

    @task(5)
    def rapid_chat_calls(self):
        """Rapid chat calls"""
        payload = {
            "message": "Quick test",
            "user_id": f"stress_{random.randint(1000, 9999)}",
            "session_id": f"session_{random.randint(1000, 9999)}"
        }
        self.client.post("/api/chat", json=payload, headers=self.auth_header)


class RicoEndUser(HttpUser):
    """Simulates end-to-end user journey (complete workflow)"""
    wait_time = between(3, 8)
    host = "https://rico-job-automation-api.onrender.com"

    auth_header = {
        "Authorization": "Bearer YOUR_API_KEY_HERE",
        "Content-Type": "application/json"
    }

    def on_start(self):
        self.user_id = f"enduser_{random.randint(10000, 99999)}"
        self.session_id = f"session_{self.user_id}"

    @task(1)
    def complete_user_journey(self):
        """Complete user journey: upload CV → get matches → chat → apply"""

        # Step 1: Upload CV
        self.client.post("/api/cv/upload", json={
            "user_id": self.user_id,
            "cv_text": "Software Engineer with 5 years experience",
            "skills": ["JavaScript", "Python", "Redis"],
            "experience_years": 5
        }, headers=self.auth_header)

        time.sleep(2)  # Wait for CV processing

        # Step 2: Get job matches
        response = self.client.get("/api/jobs?limit=10", headers=self.auth_header)
        jobs = response.json().get("jobs", []) if response.status_code == 200 else []

        if jobs:
            job_id = jobs[0].get("id", random.randint(1000, 9999))

            # Step 3: Get match score
            self.client.get(f"/api/match/{job_id}", headers=self.auth_header)

            # Step 4: Chat about the job
            self.client.post("/api/chat", json={
                "message": f"Tell me more about job {job_id}",
                "user_id": self.user_id,
                "session_id": self.session_id
            }, headers=self.auth_header)

            # Step 5: Apply
            self.client.post("/api/applications/submit", json={
                "user_id": self.user_id,
                "job_id": job_id,
                "cv_id": f"cv_{self.user_id}"
            }, headers=self.auth_header)


# Custom events for metrics
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
    print(f"Failure Rate: {total_failures/total_requests*100:.2f}%")
    if response_times:
        print(f"Avg Response Time: {sum(response_times)/len(response_times)*1000:.2f}ms")
        print(f"Max Response Time: {max(response_times)*1000:.2f}ms")
        print(f"Min Response Time: {min(response_times)*1000:.2f}ms")
    print(f"{'='*60}\n")


# Test configurations:
# 1. Normal load (realistic):
#    locust -f locustfile.py -u 50 -r 5 --run-time 5m
#
# 2. High load:
#    locust -f locustfile.py -u 100 -r 10 --run-time 5m
#
# 3. Stress test:
#    locust -f locustfile.py -u 200 -r 20 --run-time 10m
#
# 4. End-to-end journey:
#    locust -f locustfile.py RicoEndUser -u 30 -r 3 --run-time 5m
#
# 5. Distributed testing (multiple machines):
#    Master: locust -f locustfile.py --master
#    Worker: locust -f locustfile.py --worker
