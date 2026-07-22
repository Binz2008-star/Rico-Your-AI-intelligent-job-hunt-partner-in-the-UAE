# Security / Static-Analysis Audit — Refreshed 2026-07-21

**Baseline:** `main` HEAD `9fbd32c0` (PR #1268). Working tree clean.
**Provenance:** This refreshes an earlier Bandit/security pass originally run at
`55e68ad5` (#1222). Every finding below was **re-verified by direct code reading
against the current `main` SHA `9fbd32c0`** — not carried over from the prior
report. Paths and line numbers are current as of this SHA.
**Method:** read-only. `bandit -r src scripts` (1.9.4) plus targeted `file:line`
verification of each finding. No code changed.

> Why this refresh exists: the prior report's base SHA was 35 commits stale, and
> two frontend components had moved into subdirectories, so its paths no longer
> resolved. Counts and findings are otherwise substantially unchanged.

---

## Bandit 1.9.4 headline (this SHA)

`bandit -r src scripts` → **0 High · 33 Medium · 484 Low** (517 total).
Prior run at `55e68ad`: 0 / 33 / 480 (513). Drift: **+4 Low only**; High and
Medium unchanged. Top test IDs: B101=261, B110=176, B105=35, B608=26, B112=7,
B310=5, B311=4, B104=2, B107=1. **No High-severity Bandit finding.**

The +4 Low drift is `B110`/`B101` churn in new code (try/except-pass and test
asserts); it does not by itself indicate a security regression, but it is why the
report needed a refresh rather than a straight carry-over.

---

## HIGH — none reproducible

- **HIGH-1 (prior) — SSRF in `link_verifier`: CLEARED, still fixed.**
  `src/services/link_verifier.py:293` guards `if not await _is_safe_url_async(url):`
  before the first `client.get()` (`:310`), and the per-redirect guard is intact
  at `:355`. Merged in #1215; verified present at `9fbd32c`. Not reproducible.

---

## MEDIUM — all four reproducible (one partial improvement)

| ID | Status | Current `file:line` (verified on `9fbd32c`) |
|----|--------|---------------------------------------------|
| **MEDIUM-1** — urllib redirect/scheme handling (Bandit B310) | reproducible | `src/job_providers.py:234,341` · `src/jsearch_client.py:251` · `src/api/routers/paddle_billing.py:478` · `scripts/followup_smoke.py:51` (5 sites; same set and lines as prior) |
| **MEDIUM-2** — CSP is Report-Only + `unsafe-inline` | reproducible | `apps/web/next.config.js:64` emits `Content-Security-Policy-Report-Only` (not enforcing); `unsafe-inline` at `:20` (`script-src`) and `:21` (`style-src`) |
| **MEDIUM-3** — rate-limit coverage gaps | reproducible, **partially improved** | `src/api/rate_limit.py:85` `default_limits=[]` (undecorated route = unlimited). `onboarding.py` = **0** `@limiter.limit`; `user.py` (`/me`) = **0**. **Changed since prior report:** `subscription.py` now carries **1** `@limiter.limit` (was 0) — partial coverage, not full. |
| **MEDIUM-4** — container runs as root + `--reload` | **accepted — defense-in-depth, non-production** (see Remediation status) | `Dockerfile.backend:22` `CMD [... uvicorn ... "--reload"]`; **0** `USER` directives → root. NOT the production runtime: production uses Render's platform-managed native Python runtime (`render.yaml` `runtime: python`), not this image, and the configured start command has no `--reload`. (Process UID is Render-platform-managed and not asserted here — no repo evidence pins it.) The image feeds only `docker-compose` local dev, where `--reload` + the bind mount are intended. |

## LOW — all reproducible (two moved paths, one narrowed scope)

| ID | Status | Current `file:line` (verified on `9fbd32c`) |
|----|--------|---------------------------------------------|
| **LOW-1** — open-redirect via backend-supplied nav sinks | reproducible, **path moved**, scope narrowed | Now `apps/web/components/subscription/SubscriptionAtelier.tsx:593` (`window.open(req.whatsapp_url, …)`) and `:616` (`window.location.href = portal_url`). Scope is **only** these backend-supplied sinks — the prior report's `openingFilm.ts` (local constant path) and `ProfileEditorial` `new URL()` (parse, not a nav sink) are **not** open-redirects. |
| **LOW-2** — client-side draft storage (informational) | reproducible, **path moved** | Now `apps/web/components/profile/ProfileEditorial.tsx` (`sessionStorage` draft mirror, `:177`, `:865`). Not a vuln on its own; backend ignores client `rico_sid` and validates the HMAC capability cookie. |
| **LOW-3** — DNS resolution fall-open | reproducible | `src/services/link_verifier.py:117–121` `except Exception: … pass` lets an unresolvable host through the private-IP check (mirror at `:203–207` in the sync path) |

---

## False positives — unchanged, still valid

- **B608 (SQL)**: `%s` parameter binding throughout; f-strings only for
  constant/code-built fragments. No live SQL injection.
- **B104**: the literal `"0.0.0.0"` blocklist string, not a bind.
- **B105**: literals like `'PASS'`/`'FAIL'`/`""`, not credentials.
- **B101 / B311**: test asserts / non-crypto randomness.

No live SQLi, command injection, `eval`/`exec`, stored XSS, auth/role bypass, or
webhook-signature gaps were found in this pass.

---

## Remediation order (owner-set, by expected security impact)

1. **MEDIUM-1** — B310 / urllib usages, where they are real external input points
   (redirect-controlled fetch client).
2. **MEDIUM-3** — rate-limit coverage (directly affects abuse resistance).
3. **MEDIUM-2** — enforce CSP (drop Report-Only; remove `unsafe-inline`).
4. **MEDIUM-4** — container not-as-root + drop `--reload` in production images
   (if that image is used in prod).
5. **LOW-3** — DNS fall-open.
6. **LOW-1 / LOW-2** — defense-in-depth cleanup / hardening.

---

## Remediation status (updated 2026-07-21)

The findings above are the point-in-time snapshot at `9fbd32c0`. Owner-directed
remediation since then:

- **MEDIUM-1** (urllib/B310) — **accepted / false-positive.** All 5 sites use a
  hardcoded `https://` base with trusted/encoded params; none is a real external
  input point, and stdlib `urllib` blocks non-http(s)/ftp redirect schemes. No
  code change.
- **MEDIUM-3** (rate-limit coverage) — **remediated.** `@limiter.limit(LIMIT_PROFILE)`
  added to `/me`, `/onboarding/submit`, `/onboarding/status` (PR #1283, merged).
- **MEDIUM-2** (CSP Report-Only + `unsafe-inline`) — **partially remediated —
  enforcement fixed; `unsafe-inline` deferred/tracked.** Flipped to enforcing
  `Content-Security-Policy` and dropped the moot script hashes (dev-only
  `unsafe-eval` + HMR ws gated on `NODE_ENV`). `script-src`/`style-src` still
  carry `'unsafe-inline'`; removing it needs nonce-based CSP via Next.js
  middleware — a tracked follow-up (PR #1292, merged).
- **MEDIUM-4** (Docker root + `--reload`) — **accepted — defense-in-depth on a
  non-production surface.** The image is not the production runtime (Render runs
  native `runtime: python` from `render.yaml`; `Dockerfile.backend` feeds only
  `docker-compose` local dev, where `--reload` + the bind mount are intended). A
  hardening (non-root default + no `--reload`, with compose overriding to
  `root + --reload` for dev) was prepared but **not merged**: it could not be
  exercised here (sandbox blocks container-registry egress → `docker build` can't
  pull `python:3.11-slim`), and merging an unverified change to a non-production
  image is the wrong trade (PR #1295, closed unmerged). Reopen + verify in an
  environment with a Docker daemon + registry egress if the image ever becomes a
  real deploy target.
- **LOW-3** (DNS resolution fall-open) — **remediated.** Both DNS-resolution
  `except` blocks in `link_verifier.py` now fail closed (`return False`) instead
  of `pass` (PR #1302, merged).
- **LOW-1** (open-redirect via backend-supplied nav sinks) — **remediated.** The
  WhatsApp + Paddle-portal navigation targets are validated against an https +
  host allowlist (`safeExternalUrl`, `apps/web/lib/safe-external-url.ts`) before
  navigating; a disallowed or non-https value is refused with an error toast
  (this PR).
- **LOW-2** (client-side `sessionStorage` draft) — **accepted / informational.**
  Not a vulnerability on its own; the backend ignores the client `rico_sid` and
  validates the HMAC capability cookie. No code change.
