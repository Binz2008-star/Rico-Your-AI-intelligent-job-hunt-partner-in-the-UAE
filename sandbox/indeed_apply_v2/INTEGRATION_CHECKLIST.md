# Indeed Apply V2 - Integration Checklist

## Pre-Integration Requirements

### Code Quality
- [x] No hardcoded PII or sensitive data
- [x] Follows Rico coding standards
- [x] Comprehensive error handling
- [x] Proper logging implementation
- [x] Type hints where applicable
- [x] Docstrings for all public methods
- [x] No placeholder or pseudo-code

### Security
- [x] Environment variables for all sensitive data
- [x] No credentials in source code
- [x] Input validation
- [x] Rate limiting implementation
- [x] Burst protection
- [x] Auth detection
- [x] CAPTCHA detection
- [x] Cloudflare detection

### Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Dry-run tests pass
- [ ] Live tests pass (with small sample)
- [ ] Edge cases covered
- [ ] Error recovery tested
- [ ] Rate limiter tested
- [ ] Selector resilience tested

### Performance
- [ ] Performance metrics acceptable
- [ ] No memory leaks
- [ ] No resource leaks
- [ ] Browser cleanup works
- [ ] File operations atomic
- [ ] Cross-process safe

## Integration Steps

### Phase 1: Backup
- [ ] Backup `src/indeed_apply.py`
- [ ] Backup `data/ng_profile` directory
- [ ] Backup `data/applied_jobs.json`
- [ ] Document current configuration

### Phase 2: Code Migration
- [ ] Copy `sandbox/indeed_apply_v2/indeed_apply_v2.py` to `src/indeed_apply.py`
- [ ] Remove V2 prefix from environment variables
- [ ] Update `scripts/run_indeed_apply.py` to use new features
- [ ] Update `scripts/run_browser_apply.py` if needed
- [ ] Update documentation

### Phase 3: Environment Variables
- [ ] Update `.env.example` with new variables
- [ ] Update production environment variables
- [ ] Remove old variables if deprecated
- [ ] Document new variables

### Phase 4: Configuration Migration
- [ ] Migrate rate file format if needed
- [ ] Migrate profile directory if needed
- [ ] Test with existing user data
- [ ] Verify backward compatibility

### Phase 5: Testing
- [ ] Run unit tests
- [ ] Run integration tests
- [ ] Run dry-run tests
- [ ] Run live tests (staging)
- [ ] Run smoke tests
- [ ] Monitor metrics

### Phase 6: Deployment
- [ ] Deploy to staging
- [ ] Run staging tests
- [ ] Monitor for 24 hours
- [ ] Deploy to production
- [ ] Monitor for 48 hours
- [ ] Gather user feedback

### Phase 7: Post-Deployment
- [ ] Monitor success rate
- [ ] Monitor error rates
- [ ] Monitor performance metrics
- [ ] Adjust rate limits if needed
- [ ] Update documentation
- [ ] Train users on new features

## Rollback Plan

### Triggers for Rollback
- Success rate drops below 80%
- Error rate increases above 20%
- User complaints increase significantly
- Critical bugs discovered
- Performance degradation

### Rollback Steps
1. Stop production service
2. Restore `src/indeed_apply.py` from backup
3. Restore environment variables
4. Restore profile directory if needed
5. Restart service
6. Verify functionality
7. Notify users

### Rollback Verification
- [ ] Dry-run tests pass
- [ ] Live tests pass (small sample)
- [ ] No errors in logs
- [ ] Success rate normal
- [ ] User complaints resolved

## Monitoring Metrics

### Key Performance Indicators
- Success rate (target: >90%)
- Average apply time (target: <60s)
- Error rate (target: <10%)
- Daily apply count
- Retry frequency
- Adaptive cooldown effectiveness

### Alert Thresholds
- Success rate < 80% → Alert
- Error rate > 20% → Alert
- Average apply time > 120s → Warning
- Daily apply count > limit → Warning
- Cloudflare/CAPTCHA detection > 5/hour → Alert

### Log Monitoring
- Error patterns
- Retry patterns
- Detection events
- Rate limiter hits
- Recovery actions

## Success Criteria

### Functional
- [ ] All existing features work
- [ ] New features work as designed
- [ ] No regressions
- [ ] Backward compatible

### Performance
- [ ] Success rate ≥ 90%
- [ ] Error rate ≤ 10%
- [ ] Average apply time ≤ 60s
- [ ] No performance degradation

### User Experience
- [ ] Users can use without changes
- [ ] Clear error messages
- [ ] Better success rate than V1
- [ ] Fewer manual interventions

### Operational
- [ ] Easy to monitor
- [ ] Easy to debug
- [ ] Easy to rollback
- [ ] Well documented

## Post-Integration Tasks

### Documentation
- [ ] Update user documentation
- [ ] Update developer documentation
- [ ] Update API documentation
- [ ] Create troubleshooting guide
- [ ] Create FAQ

### Training
- [ ] Train support team
- [ ] Train users on new features
- [ ] Create video tutorials
- [ ] Create knowledge base articles

### Maintenance
- [ ] Schedule regular reviews
- [ ] Plan selector updates
- [ ] Plan rate limit adjustments
- [ ] Plan feature enhancements

## Sign-Off

### Development
- [ ] Code review completed
- [ ] Tests passed
- [ ] Documentation updated
- [ ] Ready for QA

### QA
- [ ] QA tests passed
- [ ] Performance validated
- [ ] Security reviewed
- [ ] Ready for staging

### Staging
- [ ] Staging tests passed
- [ ] Monitoring verified
- [ ] Rollback tested
- [ ] Ready for production

### Production
- [ ] Deployment successful
- [ ] Monitoring active
- [ ] Users notified
- [ ] Support ready

## Notes

### Known Limitations
- LLM integration requires existing scorer
- Profile data requires manual setup
- Selector changes may require updates
- Rate limits are conservative

### Future Enhancements
- Adaptive rate limiting (implemented)
- ML-based field detection
- Resume optimization
- Cover letter generation
- Multi-platform support
- Interview scheduling

### Dependencies
- Playwright (must be installed)
- python-dotenv
- filelock
- Existing Rico modules (scoring, applications, llm_scorer)

### Configuration Files
- `.env` - Environment variables
- `data/ng_profile_v2` - Browser profile
- `data/applied_jobs.json` - Application tracking
- `sandbox/indeed_apply_v2/rate.json` - Rate limiting
- `sandbox/indeed_apply_v2/metrics.json` - Performance metrics
