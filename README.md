# Job Automation System

Automated job hunting system that finds, filters, scores, and notifies you about relevant job opportunities.

## Features

- **Multi-source Job Fetching**: Scrapes jobs from Indeed, LinkedIn, and Google
- **CV-aware Intelligent Scoring**: AI-powered scoring based on candidate profile, skills, and experience
- **Weighted Skill Matching**: Prioritizes executive support, operations, compliance, and UAE experience
- **Smart Filtering**: Penalizes irrelevant roles and junior positions
- **Deduplication**: Tracks seen jobs to avoid duplicates across runs
- **Email Notifications**: Sends daily reports with high-quality matches
- **Telegram Notifications**: Real-time job alerts via Telegram bot
- **Automated Scheduler**: Runs twice daily (8:00 AM and 6:00 PM) without manual intervention
- **Custom Search**: Configurable search terms, locations, and filters

## Architecture

```
JobSpy (fetch jobs)
    ↓
Filter (remove duplicates)
    ↓
Scoring (filter good ones)
    ↓
Email + Telegram Notification (send report)
    ↓
Scheduler (automated runs)
```

## Setup

### Prerequisites

- Python 3.10+
- Gmail account with 2FA enabled
- Gmail App Password
- Telegram account (for bot notifications)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Binz2008-star/job-automation-system-1.git
cd job-automation-system-1
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables in `.env`:
```env
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_app_password
EMAIL_TO=your_email@gmail.com

TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Generate Gmail App Password

1. Enable 2FA on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate a new app password for "Mail"
4. Use the 16-character password in `.env`

### Setup Telegram Bot

1. Open Telegram and search for @BotFather
2. Send `/newbot` and follow the instructions
3. Copy the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Add the token to `.env` as `TELEGRAM_BOT_TOKEN`
5. To get your chat ID:
   - Send a message to your bot in Telegram
   - Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Find your `chat_id` in the response
   - Add it to `.env` as `TELEGRAM_CHAT_ID`

## Usage

### Manual Run

Run the job scraper manually:
```bash
python -m src.run_daily
```

### Automated Scheduler

Run the automated scheduler (runs twice daily at 8:00 AM and 6:00 PM):
```bash
python -m src.scheduler
```

The scheduler will keep running and execute the job pipeline at the scheduled times.

### Output

- Console: Shows job matches with scores
- Email: Daily report with top 10 high-quality jobs
- Telegram: Real-time job alerts with rich formatting
- Data: `data/seen_jobs.json` tracks seen jobs

## Configuration

Edit `src/job_sources.py` to customize:
- Search terms
- Location
- Number of results
- Job age filter

Edit `src/scoring.py` to adjust scoring criteria.

## Project Structure

```
job-automation-system-1/
├── src/
│   ├── job_sources.py      # Job fetching logic
│   ├── scoring.py          # CV-aware intelligent scoring algorithm
│   ├── profile.py          # Candidate profile and skill weights
│   ├── filter.py           # Deduplication system
│   ├── notifier.py         # Email notifications
│   ├── telegram_bot.py     # Telegram bot integration
│   ├── message_generator.py # Cover message templates
│   ├── run_daily.py        # Main pipeline
│   └── scheduler.py        # Automated scheduler
├── data/
│   └── seen_jobs.json      # Seen jobs database
├── .env                    # Environment variables
└── requirements.txt        # Python dependencies
```

## Current Status

✅ Phase 1: Job Fetching & Scoring
✅ Phase 2: Deduplication & Memory
✅ Phase 3: Email Notifications
✅ Phase 4: Automation (scheduled runs, Telegram integration)
✅ Phase 5: Intelligence (CV-aware scoring, weighted matching)

## Intelligent Scoring System

The system now uses a sophisticated CV-aware scoring algorithm that:

- **Analyzes Candidate Profile**: Weights skills based on experience and relevance
- **Executive Support Priority**: Highest weight (10) for executive assistant, chief of staff roles
- **Operations Focus**: Strong weight (8) for operations management positions
- **UAE Experience Bonus**: Additional points for local market knowledge
- **Smart Penalties**: Automatically filters junior, entry-level, and irrelevant roles
- **Multi-keyword Matching**: Boosts scores when multiple relevant keywords appear

**Example Scoring Results:**
- Executive Assistant to CEO: 91 points (perfect match)
- Chief of Staff: 48 points (good match)
- Operations Manager: 49 points (relevant experience)
- Junior Developer: 0 points (penalized as irrelevant)

## License

MIT
