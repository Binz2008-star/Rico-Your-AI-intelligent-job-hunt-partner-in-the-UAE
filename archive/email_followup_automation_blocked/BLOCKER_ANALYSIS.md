# Email Follow-up Automation - Blocker Analysis

**Date:** 2026-06-07  
**Status:** BLOCKED - Prerequisite Required  
**Severity:** HIGH - Architecture Blocker

---

## 🔴 Critical Blocker: User-Scoped Accessors Do Not Exist

### Root Cause Analysis

The email follow-up automation system requires user-scoped data isolation, but the current Rico codebase is **single-user only**.

### Missing Dependencies

#### 1. `get_candidate_profile(user_id=user_id)`
- **Current Implementation:** `get_candidate_profile()` (no parameters)
- **Location:** `src/profile.py:143`
- **Current Behavior:** Returns hardcoded `CANDIDATE_PROFILE` constant
- **Multi-user Safe:** ❌ NO - single-user hardcoded profile
- **Required Change:** Add user_id parameter and load user-specific profiles

#### 2. `get_applied_jobs(user_id=user_id)`
- **Current Implementation:** `get_applied_jobs()` (no parameters)
- **Location:** `src/applications.py:298`
- **Current Behavior:** Calls `load_applied_jobs()` which loads from global `data/applied_jobs.json`
- **Multi-user Safe:** ❌ NO - global file, no user isolation
- **Required Change:** Add user_id parameter and filter by user_id

### Current Architecture Limitations

```python
# Current (Single-User)
def get_candidate_profile():
    return CANDIDATE_PROFILE  # Hardcoded single user

def get_applied_jobs():
    return load_applied_jobs()  # Global file, no isolation
```

```python
# Required (Multi-User)
def get_candidate_profile(user_id: str):
    return load_user_profile(user_id)  # User-specific

def get_applied_jobs(user_id: str):
    jobs = load_applied_jobs()
    return [j for j in jobs if j.get('user_id') == user_id]  # Filtered
```

---

## 🛠️ Required Prerequisite Changes

### Phase 1: Profile Module (`src/profile.py`)

**Changes Required:**
1. Add `get_candidate_profile(user_id: str)` function
2. Load user-specific profile from database or user-scoped storage
3. Maintain backward compatibility with existing `get_candidate_profile()`
4. Add user_id to profile data model
5. Migrate existing hardcoded profile to database

**Impact:**
- Breaking change for profile access pattern
- Database schema changes required
- Migration script required
- Backward compatibility layer needed

### Phase 2: Applications Module (`src/applications.py`)

**Changes Required:**
1. Add `get_applied_jobs(user_id: str)` function
2. Add user_id field to application records
3. Filter `load_applied_jobs()` results by user_id
4. Or migrate to user-scoped database storage
5. Maintain backward compatibility with existing `get_applied_jobs()`

**Impact:**
- Breaking change for application access pattern
- Data model changes required
- Migration script required
- File-based storage may need database migration

### Phase 3: Data Model Migration

**Changes Required:**
1. Add user_id to application data model
2. Migrate existing single-user data to multi-user structure
3. Update all application creation points to include user_id
4. Update all application query points to filter by user_id
5. Add user_id validation and constraints

**Impact:**
- Major data migration
- All application-related code updates
- Database schema changes
- Potential data loss if migration fails

---

## 🚨 Why This Cannot Be Bypassed

### Security Concerns
- **Data Leakage:** Without user-scoped accessors, users can see each other's applications
- **Privacy Violation:** User A could access User B's follow-up history
- **Compliance Risk:** GDPR and privacy regulations require data isolation

### Functional Concerns
- **Incorrect Results:** Follow-up logic would process all users' applications together
- **Rate Limiting:** Global rate limits instead of per-user rate limits
- **Opt-in Violation:** Cannot enforce per-user opt-in preferences

### Production Risk
- **Data Corruption:** Multi-user writes to single-user storage
- **Race Conditions:** Concurrent access without user isolation
- **Audit Trail:** Cannot track which user performed which action

---

## 📋 Alternative Approaches Considered

### Option 1: Add user_id Parameter Only
**Pros:** Minimal code change
**Cons:** Still requires underlying multi-user architecture
**Verdict:** ❌ Insufficient - still needs data model changes

### Option 2: Use Global Profile for Now
**Pros:** Quick implementation
**Cons:** Security risk, data leakage, privacy violation
**Verdict:** ❌ Unacceptable - violates security principles

### Option 3: Implement Full Multi-User Architecture
**Pros:** Proper solution, production-ready
**Cons:** Major effort, breaking changes
**Verdict:** ✅ Required - only acceptable path

---

## 🎯 Recommended Action Plan

### Step 1: Prerequisite PR (Required)
**Branch:** `feat/user-scoped-accessors`
**Scope:**
- Add `get_candidate_profile(user_id: str)` to `src/profile.py`
- Add `get_applied_jobs(user_id: str)` to `src/applications.py`
- Add user_id to application data model
- Migrate existing data to multi-user structure
- Maintain backward compatibility

**Estimated Effort:** 2-3 days
**Risk Level:** MEDIUM
**Dependencies:** None

### Step 2: Re-scope Email Follow-up (After Step 1)
**Branch:** `feat/followup-preview`
**Scope:**
- Read-only preview engine only
- No Gmail integration
- No email sending
- No database writes
- User-scoped using new accessors

**Estimated Effort:** 1-2 days
**Risk Level:** LOW
**Dependencies:** Step 1

### Step 3: Full Email Follow-up (Future)
**Branch:** `feat/email-followup-automation`
**Scope:**
- Gmail integration
- Email sending
- Database writes
- Full automation

**Estimated Effort:** 3-5 days
**Risk Level:** HIGH
**Dependencies:** Step 1 + Step 2

---

## 📊 Impact Assessment

### Without Prerequisite
- **Security Risk:** CRITICAL - data leakage
- **Privacy Risk:** CRITICAL - GDPR violation
- **Functional Risk:** HIGH - incorrect behavior
- **Production Risk:** CRITICAL - data corruption

### With Prerequisite
- **Security Risk:** LOW - proper isolation
- **Privacy Risk:** LOW - compliant with regulations
- **Functional Risk:** LOW - correct behavior
- **Production Risk:** LOW - proper architecture

---

## 🔐 Compliance Notes

### GDPR Requirements
- **Article 32:** Data security by design and by default
- **Article 25:** Data protection by design and by default
- **Article 32:** Appropriate technical measures

**Current State:** ❌ NON-COMPLIANT
**Required State:** ✅ COMPLIANT (with user-scoped accessors)

### Privacy Principles
- **Data Minimization:** Only access user's own data
- **Purpose Limitation:** Use data only for intended purpose
- **Storage Limitation:** Do not store unnecessary data
- **Integrity and Confidentiality:** Protect user data

**Current State:** ❌ VIOLATES PRINCIPLES
**Required State:** ✅ COMPLIES (with user-scoped accessors)

---

## 📝 Conclusion

**Status:** BLOCKED - Cannot proceed without prerequisite

**Reason:** Email follow-up automation requires user-scoped data isolation, which does not exist in current Rico architecture.

**Required Action:** Implement user-scoped accessors as prerequisite PR before any email follow-up work.

**Timeline:** 2-3 days for prerequisite, then 1-2 days for re-scoped follow-up preview.

**Risk:** Proceeding without prerequisite would create critical security and privacy violations.

---

**Generated:** 2026-06-07  
**Next Review:** After prerequisite PR completion
