import os
import requests
from dotenv import load_dotenv

load_dotenv()

TARGET_QUERIES = [
    "Executive Assistant CEO UAE",
    "Operations Manager UAE",
    "Chief of Staff UAE",
    "Founder Office Manager UAE",
    "Compliance Operations Manager UAE",
    "VIP Relationship Manager UAE",
]


def _normalise_job(job):
    return {
        "title": job.get("job_title"),
        "company": job.get("employer_name"),
        "location": job.get("job_city") or job.get("job_country"),
        "description": job.get("job_description") or "",
        "link": job.get("job_apply_link") or job.get("job_google_link"),
        "source": "JSearch",
    }


def search_jsearch(query):
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        raise RuntimeError("Missing RAPIDAPI_KEY. Add it in GitHub Secrets or a local .env file.")

    url = "https://jsearch.p.rapidapi.com/search-v2"
    params = {
        "query": query,
        "country": "ae",
        "page": "1",
        "num_pages": "1",
        "date_posted": "week",
    }
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)
    if response.status_code != 200:
        print(f"JSearch error {response.status_code}: {response.text[:200]}")
        return []

    data = response.json()
    return [_normalise_job(job) for job in data.get("data", [])]


def get_jobs():
    seen = set()
    jobs = []

    for query in TARGET_QUERIES:
        for job in search_jsearch(query):
            key = (job.get("title"), job.get("company"), job.get("link"))
            if key not in seen:
                seen.add(key)
                jobs.append(job)

    return jobs
