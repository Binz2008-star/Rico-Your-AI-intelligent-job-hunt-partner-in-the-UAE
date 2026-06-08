# LinkedIn Easy Apply V2

## Overview

LinkedIn Easy Apply V2 is an enhanced version of the LinkedIn automation system with advanced features for improved reliability and performance.

## Key Features

### 1. Adaptive Rate Limiting
- **Dynamic cooldown adjustment**: Cooldown period adjusts based on success rate
- **Burst protection**: Maximum 3 applies in 30 seconds to avoid detection
- **Success rate tracking**: Monitors recent apply success/failure ratio
- **Smart adaptation**: 
  - Low success rate (<50%) → Increase cooldown (up to 3x)
  - High success rate (>80%) → Decrease cooldown (down to 0.5x)

### 2. Enhanced Error Recovery
- **3 recovery strategies**:
  - `wait`: Simple delay for transient issues
  - `refresh_page`: Reload page for network issues
  - `new_context`: Create new browser context for auth/CAPTCHA issues
- **Exponential backoff**: (2^attempt) * 5 seconds between retries
- **Smart error classification**: Network, CAPTCHA, auth, unknown
- **Max retries**: Configurable (default: 2)

### 3. Comprehensive Monitoring
- **Performance metrics**:
  - Jobs scanned
  - Easy Apply found
  - Applied/Failed/Skipped counts
  - Success rate
  - Average apply time
- **History tracking**: Last 100 runs stored
- **Success rate trend**: Track improvement over time
- **Structured logging**: File-based logs with rotation

### 4. Enhanced Selectors
- **Multiple fallbacks**: 3-4 fallback selectors per element
- **Resilient to UI changes**: If one selector fails, tries others
- **Coverage**:
  - Login: Email, password, button (3 each)
  - Apply: Easy Apply button, modal, next/review/submit buttons (3-4 each)
  - Success/CAPTCHA detection (3-4 each)

### 5. Detection Systems
- **CAPTCHA detection**: Multiple selector patterns
- **Auth detection**: URL-based detection
- **Error classification**: Smart error type identification

## Architecture

```
src/auto_apply_v2.py
├── Config
│   ├── Environment variables
│   └── Rate limiting settings
├── Status Enums
│   └── ApplyStatus (SUCCESS, FAILED, RETRY_EXHAUSTED, etc.)
├── Performance Metrics
│   ├── PerformanceMetrics dataclass
│   └── MetricsTracker class
├── Rate Limiter
│   └── _RateLimiterV2 (adaptive cooldown)
├── Selectors
│   └── _LiV2 (fallback selectors)
├── Detection
│   ├── _detect_captcha()
│   └── _detect_auth_required()
├── Error Recovery
│   ├── _get_recovery_action()
│   └── _apply_recovery()
└── Engine
    └── LinkedInEasyApplyEngineV2
```

## Configuration

### Environment Variables

```bash
# LinkedIn Credentials
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password

# Auto-Apply Configuration
AUTO_APPLY_ENABLED=true
AUTO_APPLY_DRY_RUN=false
AUTO_APPLY_MAX_PER_RUN=5
AUTO_APPLY_SCORE_THRESHOLD=75
AUTO_APPLY_COOLDOWN_SECONDS=90
AUTO_APPLY_DAILY_LIMIT=30
ALLOW_CI_APPLY=false

# CV Path
CV_PATH=data/cv.pdf

# Exclusion Keywords
AUTO_APPLY_EXCLUDE_KEYWORDS=uae national,uae nationals only,emirati only,intern,internship
```

## Usage

### Basic Usage

```python
from src.auto_apply_v2 import run_auto_apply_v2

jobs = [
    {
        "title": "HSE Manager",
        "company": "Test Company",
        "link": "https://www.linkedin.com/jobs/view/123456789",
        "score": 85,
        "description": "Job description",
        "location": "Dubai, UAE",
    }
]

results = run_auto_apply_v2(jobs, max_applies=3, headless=False)
```

### With Context Manager

```python
from src.auto_apply_v2 import LinkedInEasyApplyEngineV2

with LinkedInEasyApplyEngineV2(headless=False) as engine:
    results = engine.apply_batch(jobs, max_applies=3)
```

### Dry-Run Mode

```python
import os
os.environ["AUTO_APPLY_DRY_RUN"] = "true"
os.environ["AUTO_APPLY_ENABLED"] = "true"

results = run_auto_apply_v2(jobs, max_applies=3)
```

## Testing

### Run Unit Tests

```bash
python scripts/test_linkedin_v2.py
```

### Run Dry-Run Test

```bash
python scripts/test_linkedin_v2_dryrun.py
```

### Test Coverage

- ✅ Profile validation
- ✅ Adaptive rate limiting
- ✅ Metrics tracking
- ✅ Selector definitions
- ✅ Dry-run mode

## Monitoring

### Metrics Files

- **Rate limiter state**: `data/auto_apply_rate_v2.json`
- **Performance metrics**: `data/auto_apply_metrics_v2.json`
- **Logs**: `data/logs/`

### Metrics Tracked

```python
{
    "jobs_scanned": 10,
    "easy_apply_found": 5,
    "applied": 2,
    "failed": 1,
    "skipped": 1,
    "total_duration_seconds": 120.5,
    "avg_apply_time_seconds": 40.2,
    "success_rate": 0.667
}
```

## Error Handling

### Retry Logic

1. **First attempt**: Try apply
2. **On failure**: Classify error type
3. **Recovery action**: Apply appropriate recovery strategy
4. **Backoff**: Wait (2^attempt) * 5 seconds
5. **Retry**: Try again (up to max_retries)
6. **Exhausted**: Return RETRY_EXHAUSTED status

### Error Types

- **Network**: Timeout, connection issues → refresh_page
- **CAPTCHA**: CAPTCHA detected → new_context
- **Auth**: Login required → new_context
- **Unknown**: Generic error → wait

## Comparison with V1

| Feature | V1 | V2 |
|---------|----|----|
| Rate Limiting | Fixed cooldown | Adaptive cooldown |
| Error Recovery | Basic retry | 3 recovery strategies |
| Monitoring | Basic logging | Comprehensive metrics |
| Selectors | Single selector | 3-4 fallbacks |
| Detection | Basic | CAPTCHA/Auth detection |
| History | None | Last 100 runs |
| Success Rate | Not tracked | Tracked and displayed |

## Integration with Main System

### Step 1: Update Daily Pipeline

In `src/run_daily.py`, replace:

```python
from src.auto_apply import run_auto_apply
```

With:

```python
from src.auto_apply_v2 import run_auto_apply_v2
```

### Step 2: Update Function Call

Replace:

```python
run_auto_apply(jobs, max_applies=MAX_APPLIES)
```

With:

```python
run_auto_apply_v2(jobs, max_applies=MAX_APPLIES)
```

### Step 3: Test

Run dry-run test to verify integration:

```bash
AUTO_APPLY_DRY_RUN=true python scripts/run_daily.py
```

## Troubleshooting

### Issue: Rate limiter blocking applies

**Solution**: Check cooldown settings and burst protection

```bash
# Check current cooldown
grep AUTO_APPLY_COOLDOWN_SECONDS .env

# Temporarily reduce for testing
AUTO_APPLY_COOLDOWN_SECONDS=30
```

### Issue: CAPTCHA detected

**Solution**: 
1. Wait a few minutes
2. Try with new browser context
3. Consider using residential IP

### Issue: Login failed

**Solution**:
1. Verify credentials in `.env`
2. Check if LinkedIn requires 2FA
3. Try manual login first

### Issue: Selectors not found

**Solution**: V2 has fallback selectors, but if all fail:
1. Check if LinkedIn UI changed
2. Update selectors in `_LiV2` class
3. Run test to verify

## Performance

### Expected Performance

- **Apply time**: 30-60 seconds per job
- **Success rate**: 70-90% (depends on job quality)
- **Rate limit**: 30 jobs/day, 90s cooldown
- **Burst limit**: 3 jobs in 30s

### Optimization Tips

1. **Use high-quality jobs**: Score threshold 75+
2. **Avoid excluded keywords**: Update exclusion list
3. **Monitor success rate**: Adjust cooldown based on results
4. **Use dry-run first**: Test before live applies

## Security

### Best Practices

1. **Never commit credentials**: `.env` is in `.gitignore`
2. **Use 2FA**: Enable 2FA on LinkedIn account
3. **Monitor usage**: Check metrics regularly
4. **Respect limits**: Don't exceed daily limits
5. **Use residential IP**: Avoid datacenter IPs

## Future Enhancements

- [ ] ML-based field detection
- [ ] Resume optimization
- [ ] Cover letter generation
- [ ] Interview scheduling
- [ ] Multi-platform support
- [ ] Dashboard integration

## Support

For issues or questions:
1. Check logs in `data/logs/`
2. Review metrics in `data/auto_apply_metrics_v2.json`
3. Run test suite: `python scripts/test_linkedin_v2.py`
4. Check documentation in `CLAUDE.md`

## License

Part of Rico Hunt - AI Job Search Automation System
