def score_job(job):
    score = 0
    title = (job.get("title") or "").lower()

    if "executive" in title:
        score += 30
    if "assistant" in title or "operations" in title:
        score += 25
    if "ceo" in title or "founder" in title:
        score += 20

    return score