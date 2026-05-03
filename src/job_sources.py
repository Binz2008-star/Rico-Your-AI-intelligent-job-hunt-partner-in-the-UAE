from jobspy import scrape_jobs


def get_jobs():
    jobs_df = scrape_jobs(
        site_name=["indeed", "linkedin", "google"],
        search_term="Executive Assistant to CEO OR Founder Office Manager OR Chief of Staff OR Executive Operations Manager OR Operations Manager OR Compliance Operations Manager OR VIP Relationship Manager OR Private Office Executive Assistant",
        location="UAE",
        results_wanted=30,
        hours_old=24,
        country_indeed="united arab emirates"
    )

    jobs = []

    for _, row in jobs_df.iterrows():
        jobs.append({
            "title": row.get("title"),
            "company": row.get("company"),
            "location": row.get("location"),
            "link": row.get("job_url"),
            "description": row.get("description")
        })

    return jobs
