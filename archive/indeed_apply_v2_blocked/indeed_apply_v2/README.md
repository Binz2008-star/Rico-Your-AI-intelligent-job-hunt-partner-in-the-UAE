# Indeed Apply V2 - Enhanced Version

## Overview

This is an enhanced version of the Indeed Easy Apply automation system, developed in a sandbox environment for testing before integration into the main Rico codebase.

## Improvements Over V1

### 1. Enhanced Selector Resilience
- Multiple fallback selectors for each element
- Added Indeed-specific CSS classes (e.g., `.css-1e61u6i`, `.css-1wc71we`)
- Better handling of dynamic class names
- Enhanced iframe detection with multiple patterns

### 2. Improved Error Handling
- Specific error types (network, form, captcha, cloudflare)
- Detailed error details in results
- Better error logging with context
- Error indicator detection in forms

### 3. Retry Logic with Exponential Backoff
- Configurable max retries (`INDEED_V2_MAX_RETRIES`)
- Exponential backoff: `(2^attempt) * 5` seconds
- Retry on network errors, form errors, submit failures
- Retry exhaustion status tracking

### 4. Profile Data Validation
- Pre-flight validation of required fields
- Clear error messages for missing data
- Validates: name, email, street address
- Prevents failed applies due to missing data

### 5. Enhanced Detection Systems
- **Cloudflare detection**: "just a moment", "checking your browser"
- **CAPTCHA detection**: Multiple captcha selector patterns
- **Auth detection**: Enhanced URL and text patterns
- **Error detection**: Form error indicators

### 6. Burst Protection
- Prevents burst applies (more than 3 in 30 seconds)
- Separate from daily rate limiting
- Protects against detection

### 7. LLM-Powered Screening Questions
- Detects screening questions in apply forms
- Uses existing LLM scorer to answer questions
- Integrates with candidate profile
- Limits to 5 questions per form

### 8. Enhanced Rate Limiter
- Burst protection on top of daily limits
- Better state management
- Atomic file operations
- Cross-process safe

### 9. Debug Mode
- Detailed logging when enabled
- Step-by-step form navigation logging
- Selector detection logging
- Error context logging

### 10. Improved Statistics
- Tracks: total scanned, easy apply found, title filtered, applied, failed, skipped
- Per-run statistics reporting
- Better visibility into system performance

## Environment Variables

### Core Configuration
```bash
INDEED_V2_ENABLED=false              # Master switch
INDEED_V2_DRY_RUN=false              # Dry run mode
INDEED_V2_HEADLESS=false             # Visible browser
INDEED_V2_DEBUG=false                # Debug logging
```

### Rate Limiting
```bash
INDEED_V2_MAX_PER_RUN=3              # Max applications per run
INDEED_V2_DAILY_LIMIT=15             # Daily limit
INDEED_V2_COOLDOWN_SECONDS=120       # Cooldown between applies
INDEED_V2_MAX_RETRIES=2              # Max retry attempts
```

### Anti-Detection
```bash
INDEED_V2_SLOW_MO=800                # Slow motion (ms)
INDEED_V2_MAX_JOB_AGE_DAYS=14        # Max job age
```

### Scoring
```bash
INDEED_V2_SCORE_THRESHOLD=0          # Score threshold
```

### Profile Data (Required for Live Apply)
```bash
INDEED_V2_NAME=                      # Full name
INDEED_V2_EMAIL=                     # Email address
INDEED_V2_PHONE=                     # Phone number (optional)
INDEED_V2_STREET_ADDRESS=            # Street address
INDEED_V2_RELEVANT_JOB_TITLE=       # Current/relevant job title
INDEED_V2_RELEVANT_COMPANY=         # Current/relevant company
```

### Paths
```bash
NG_PROFILE_DIR=data/ng_profile_v2    # Persistent browser profile
CV_PATH=data/cv.pdf                  # CV file path
INDEED_V2_SKIP_COMPANIES=           # Comma-separated companies to skip
```

## Usage

### Testing

```bash
# Test profile validation only
python sandbox/indeed_apply_v2/test_v2.py --profile-only

# Test selector detection only
python sandbox/indeed_apply_v2/test_v2.py --selectors-only

# Test dry run (scanning only)
python sandbox/indeed_apply_v2/test_v2.py --dry-run

# Test dry run with debug logging
python sandbox/indeed_apply_v2/test_v2.py --dry-run --debug

# Test live apply (1 application)
python sandbox/indeed_apply_v2/test_v2.py --live --max 1
```

### Direct Usage

```python
from sandbox.indeed_apply_v2.indeed_apply_v2 import run_indeed_apply_v2

# Dry run
results = run_indeed_apply_v2(dry_run=True, max_applies=10)

# Live apply
results = run_indeed_apply_v2(dry_run=False, max_applies=3)
```

## Integration Plan

### Phase 1: Testing (Current)
- [x] Create sandbox version
- [x] Add enhanced features
- [x] Create test suite
- [ ] Run dry-run tests
- [ ] Run live tests with small sample
- [ ] Validate all improvements work as expected

### Phase 2: Code Review
- [ ] Review code for Rico coding standards
- [ ] Ensure no hardcoded PII
- [ ] Verify security practices
- [ ] Check error handling completeness
- [ ] Validate logging appropriateness

### Phase 3: Integration
- [ ] Replace `src/indeed_apply.py` with V2
- [ ] Update environment variable names (remove V2 prefix)
- [ ] Update `scripts/run_indeed_apply.py` to use V2
- [ ] Update documentation
- [ ] Update CI/CD if needed

### Phase 4: Migration
- [ ] Backup existing profile directory
- [ ] Migrate rate file format if needed
- [ ] Test with existing users
- [ ] Monitor for issues
- [ ] Rollback plan if needed

### Phase 5: Deployment
- [ ] Deploy to staging
- [ ] Run smoke tests
- [ ] Deploy to production
- [ ] Monitor metrics
- [ ] Gather feedback

## Backward Compatibility

The V2 version maintains backward compatibility with:
- Same job data structure
- Same result structure (with additional fields)
- Same rate file format
- Same profile directory structure

The main differences are:
- Environment variable names (V2 prefix)
- Additional result fields (retry_count, error_details)
- Additional status types
- Enhanced statistics

## Rollback Plan

If V2 causes issues:
1. Revert `src/indeed_apply.py` to V1
2. Revert environment variable names
3. Restore backup of profile directory
4. Notify users of rollback

## Monitoring

Key metrics to monitor:
- Success rate vs V1
- Error rate by type
- Retry frequency
- Rate limiter hits
- Detection events (cloudflare, captcha)
- Average apply time

## Known Limitations

1. **LLM Integration**: Screening question answering requires existing LLM scorer
2. **Profile Data**: Requires manual setup of profile environment variables
3. **Indeed Changes**: Selector changes may require updates
4. **Rate Limits**: Daily limits are conservative, may need adjustment
5. **Browser Profile**: Requires periodic login refresh

## Future Enhancements

1. **Adaptive Rate Limiting**: Adjust based on success rate
2. **Machine Learning**: Learn from successful applies
3. **Multi-Platform**: Extend to other job boards
4. **Resume Optimization**: Auto-generate tailored resumes
5. **Cover Letter Generation**: LLM-powered cover letters
6. **Interview Scheduling**: Auto-schedule interviews
7. **Follow-up Automation**: Automated follow-up emails

## Support

For issues or questions:
1. Check debug logs with `INDEED_V2_DEBUG=true`
2. Run test suite: `python sandbox/indeed_apply_v2/test_v2.py --debug`
3. Review Indeed job page for selector changes
4. Check profile data completeness
5. Verify rate limiter state

## License

Same as Rico project license.
