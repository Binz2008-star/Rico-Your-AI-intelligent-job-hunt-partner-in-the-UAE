# Code Review Improvements - Split Plan

**Date:** 2026-06-07  
**Status:** Planning Phase

---

## 📋 Original Mixed PR (NOT APPROVED)

**Files to Split:**
- `src/run_daily.py` - Prometheus metrics
- `src/cover_letter_writer.py` - Null safety + performance
- `src/application_documents.py` - Error handling + validation
- `src/resume_optimizer.py` - Logging + API key compatibility
- `scripts/test_linkedin_scraper.py` - Environment isolation (❌ NOT FOR PRODUCTION)

---

## ✅ Approved Split PRs

### PR #1: run_daily.py Prometheus Metrics Only
**Branch:** `refactor/run-daily-prometheus-metrics`
**Files:**
- `src/run_daily.py`

**Changes:**
- Remove module-level Prometheus initialization (lines 101-113)
- Rely solely on lazy initialization in `_init_metrics()`
- Fix double initialization issue

**Scope:**
- Prometheus metrics consolidation only
- No other changes to run_daily.py

**Tests Required:**
- Verify Prometheus metrics still initialize correctly
- Verify no double initialization

**Status:** ⏳ PENDING - Needs branch creation

---

### PR #2: cover_letter_writer.py Null Safety Only
**Branch:** `refactor/cover-letter-null-safety`
**Files:**
- `src/cover_letter_writer.py`

**Changes:**
- Add null checks for missing fields
- Handle None values gracefully
- Performance optimizations

**Scope:**
- Null safety only
- No other changes

**Tests Required:**
- Test with None/null inputs
- Verify no crashes on missing data

**Status:** ⏳ PENDING - Needs branch creation

---

### PR #3: application_documents.py Validation/Error Handling Only
**Branch:** `refactor/application-documents-validation`
**Files:**
- `src/application_documents.py`

**Changes:**
- Enhanced error handling
- Input validation
- Dependency injection improvements

**Scope:**
- Validation and error handling only
- No other changes

**Tests Required:**
- Test validation logic
- Test error handling paths

**Status:** ⏳ PENDING - Needs branch creation

---

### PR #4: resume_optimizer.py Logging/API-Key Compatibility Only
**Branch:** `refactor/resume-optimizer-logging-apikey`
**Files:**
- `src/resume_optimizer.py`

**Changes:**
- Logging standards improvements
- Null safety
- API key compatibility

**Scope:**
- Logging and API key compatibility only
- No other changes

**Tests Required:**
- Verify logging output
- Test API key handling

**Status:** ⏳ PENDING - Needs branch creation

---

## ❌ LinkedIn Scraper (NOT FOR PRODUCTION)

**File:** `scripts/test_linkedin_scraper.py`

**Action Required:**
- Move to `experiments/linkedin/` OR `scripts/manual/`
- Add warning header: "MANUAL-ONLY - NOT PRODUCTION SUPPORTED"
- Do NOT include in any production PR

**Reason:**
- LinkedIn prohibits scraping
- High compliance risk
- Should remain as sandbox/POC only

**Status:** ⏳ PENDING - Needs move

---

## 📊 Split Summary

| Original File | Split PR | Branch | Status |
|---------------|---------|--------|--------|
| run_daily.py | PR #1 | refactor/run-daily-prometheus-metrics | ⏳ Pending |
| cover_letter_writer.py | PR #2 | refactor/cover-letter-null-safety | ⏳ Pending |
| application_documents.py | PR #3 | refactor/application-documents-validation | ⏳ Pending |
| resume_optimizer.py | PR #4 | refactor/resume-optimizer-logging-apikey | ⏳ Pending |
| test_linkedin_scraper.py | ❌ Move to experiments/ | - | ⏳ Pending |

---

## 🎯 Execution Order

**Prerequisites (from user):**
1. Wait for #500 review/merge/smoke
2. Wait for #501 review/merge/smoke
3. Open Creative bypass draft for review
4. Job Source Adapter Foundation reviewed separately

**After Prerequisites:**
1. Move LinkedIn scraper to experiments/ or scripts/manual/
2. Create PR #1 (run_daily.py)
3. Create PR #2 (cover_letter_writer.py)
4. Create PR #3 (application_documents.py)
5. Create PR #4 (resume_optimizer.py)

**All PRs:**
- Draft first
- Tests required per PR
- One concern per PR
- No runtime behavior change unless explicitly reviewed

---

## 📝 Notes

**Rules:**
- No LinkedIn scraper in production PRs
- No browser automation
- No user credentials
- No CI scraping
- No frontend exposure
- No scheduler
- One PR per concern
- Draft first
- Tests required per PR

**Current Status:**
- All changes are currently in the workspace
- Need to create separate branches for each PR
- Need to move LinkedIn scraper out of production path

---

**Generated:** 2026-06-07  
**Next Step:** Wait for prerequisites, then execute split plan
