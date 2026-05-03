import requests
import os
from dotenv import load_dotenv

load_dotenv()


def send_telegram_message(message: str) -> bool:
    """Send message via Telegram Bot API. Returns True if successful, False otherwise."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not all([bot_token, chat_id]):
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env file")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        print("Telegram message sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")
        return False


def format_telegram_jobs(jobs_with_scores) -> str:
    """Format jobs for Telegram message with HTML formatting."""
    if not jobs_with_scores:
        return "<b>No new jobs found today.</b>"
    
    lines = [
        "<b>🔔 Job Hunting Daily Report</b>",
        f"Found {len(jobs_with_scores)} high-quality job matches",
        ""
    ]
    
    for job, score in jobs_with_scores[:10]:
        title = job.get('title', 'N/A').replace('<', '&lt;').replace('>', '&gt;')
        company = job.get('company', 'N/A').replace('<', '&lt;').replace('>', '&gt;')
        location = job.get('location', 'N/A').replace('<', '&lt;').replace('>', '&gt;')
        link = job.get('link', 'N/A')
        
        lines.extend([
            f"<b>📌 {title}</b>",
            f"🏢 {company}",
            f"📍 {location}",
            f"⭐ Score: {score}",
            f"🔗 <a href='{link}'>Apply</a>",
            ""
        ])
    
    return "\n".join(lines)
