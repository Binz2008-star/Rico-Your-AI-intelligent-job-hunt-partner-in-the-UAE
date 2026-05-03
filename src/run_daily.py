from src.job_sources import get_jobs
from src.scoring import score_job
from src.message_generator import generate_message


def main():
    jobs = get_jobs()
    matches = []

    for job in jobs:
        score = score_job(job)
        if score >= 70:
            matches.append((job, score))

    matches.sort(key=lambda x: x[1], reverse=True)

    print(f"Found {len(matches)} high-quality matches")

    for job, score in matches[:20]:
        print("\n=== JOB MATCH ===")
        print(job.get("title"), "-", job.get("company"))
        print("Location:", job.get("location"))
        print("Score:", score)
        print("Apply:", job.get("link"))
        print(generate_message(job))


if __name__ == "__main__":
    main()
