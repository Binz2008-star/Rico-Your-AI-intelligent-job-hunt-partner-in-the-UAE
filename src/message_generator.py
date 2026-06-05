def generate_message(job):
    title = job.get("title") or "this"
    return f"I am interested in the {title} role and would like to apply."