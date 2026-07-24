# Rico Competitive Differentiation — Grounded Gap Analysis & Sequencing

**Recorded:** 2026-07-24
**Origin:** Owner (Roben) chat vision, 2026-07-24 — "how Rico becomes genuinely
distinctive, not just CV + jobs + tracker like Huntr/Teal."
**Status:** Proposal / roadmap — **not** scoped into tasks (per DEC-20260721-001
"no bulk task conversion"; each slice creates its own task at cut time).
**Governance:** Subject to the active feature lock **DEC-20260723-001** — *no new
features until trust + execution reliability are fixed.* This document classifies
each idea as **allowed-now (trust engine)** vs **deferred (staged)** against that
lock and DEC-20260721-001's five-stage order.
**Grounded against:** `origin/main` `97c5f6f6` (2026-07-24). PR #1373 (frontend-only
Applications board + `/queue` Atelier a11y) and PR #1372 (the owner-only subscriber
administration surface — admin subscriber router/repo, auth plumbing, and owner-nav
UI) are both included; **neither modified any cited career-memory, matching,
eligibility, provenance, or strategy module**, so every citation below remains valid
on this SHA. Code references were found by targeted search, not an exhaustive
audit — verify the cited module still matches before building on it.

---

## Executive summary (الخلاصة)

> رؤية التميّز التي طرحها المالك ليست فكرة جديدة يُبنى من الصفر — هي **بالفعل**
> استراتيجية Rico المسجّلة (`DEC-20260723-001`: محرّك الثقة هو الخندق). **عدّة
> مكوّنات أساسية موجودة جزئيًا** وطبقة الـ provenance قيد التطوير النشط (شرائح
> #1364–1368، #1336)؛ الفجوات المنتَجية المتبقّية موثّقة أدناه. التمايز المطلوب هو
> ما ينفّذه الفريق أصلًا تحت قفل "الثقة أولًا". ثلاث من النقاط السبع = محرّك الثقة
> (مسموحة الآن)؛ أربع مؤجّلة بالتسلسل المسجّل.

The owner's proposal maps almost one-to-one onto Rico's already-recorded strategy
(`CAREER_OS_VISION.md` 10-layer Career OS + `DEC-20260723-001` trust-first moat +
`DEC-20260721-001` five-stage order). **Several foundational components exist
partially; the remaining product gaps are documented below** — and the
provenance/evidence layer is being actively built this week (#1364–1368, #1336).
"Partial" is the operative word: the cited modules provide scaffolding (data
stores, verdict/confidence scaffolds, eligibility markers), **not** the finished
user-facing capability each proposal describes. The differentiation the owner
wants **is** the current roadmap — the value of this document is to (a) stop
anyone re-implementing what exists, (b) name the *real* remaining gaps precisely,
and (c) sequence them so trust-aligned work proceeds under the lock while
genuinely-new features wait for their stage.

---

## Owner's 7 proposals (preserved)

1. **Career Memory** — long-term professional memory with per-fact provenance
   ("this line came from your real CV / a documented achievement, not invented").
2. **UAE Intelligence Engine** — resident vs Emirati-only, UAE driving licence,
   salary sanity by emirate, misleading titles, Gulf-experience requirement,
   company trust, duplicate/stale postings, apply-via-company-site vs platform.
3. **Explainable matching** — not just `82%`; show **strong match / missing /
   verdict**, and be honest: *"Apply, but do not rewrite your CV to claim the
   missing requirements."*
4. **Application Strategy (not random auto-apply)** — best 5/day, tailored CV per
   role, why-it's-worth-it, no duplicate applies, apply-now-vs-recruiter-first,
   auto follow-up. Motto: *Apply smarter, not everywhere.*
5. **Evidence Vault** — every strong CV claim linked to a source (certificate,
   contract, reference, project, sales number, ISO) and clickable to its origin.
6. **Recruiter Mode** — find the right hiring contact, company-specific outreach,
   track who was contacted, follow-up reminders, interview prep by person/company.
7. **Outcome Learning** — after interview/reject/ignore/offer, learn which CV /
   title / salary / platform / company-type worked, and adjust strategy.

Owner's stated priority order: UAE Intelligence → Career Memory+provenance →
Explainable matching → Outcome learning → Evidence-backed CV → Recruiter outreach
→ Controlled assisted apply.

---

## Gap analysis (proposal → existing code → real gap → verdict)

| # | Proposal | Already in code (`main` 97c5f6f6) | The real gap | Strategy anchor | Lock verdict |
|---|----------|-----------------------------------|--------------|-----------------|--------------|
| 1 | Career Memory + provenance | `src/services/career_memory.py` (CAREER-OS-09: records apply/save/skip/block, recalls blocked/frequently-skipped companies, injects memory context), `src/services/career_context.py`, program doc `CAREER_CONTEXT_PROGRAM.md` | No **per-fact provenance** on CV claims (source of each line); memory is action-history, not a sourced career store | `DEC-20260723-001` §5 "source/date/confidence"; `DEC-20260721-001` stage 2 (durable memory) | **Allowed-now** (trust) — but coordinate with the live `career_context` program |
| 2 | UAE Intelligence | `src/eligibility_filter.py` (UAE-nationals-only, EN+AR markers), `src/job_integrity.py`, `src/services/matching_guardrails.py`, `src/services/source_quality.py`, `src/services/job_link_trust.py`, `src/services/search_dedup.py` (dedupe), `RICO_INTELLIGENCE_PHASE1.md` | No **salary-sanity by emirate**, **driving-licence-required** detector, **misleading-title** flag, or **apply-via-company-site** hint (targeted search found none — verify) | `DEC-20260721-001` stage 3 (UAE data moat) | **Mostly deferred** (stage 3). *Exception:* honest eligibility flags surfaced to the user are trust-aligned and allowed |
| 3 | Explainable matching | `src/services/job_match_explanation.py::build_match_explanation` (emits `verdict`, `confidence`, `summary`, `next_step`, matched-skills overlap, seniority-mismatch note), `src/rico_match_explainer.py`, `src/scoring.py` | **Matched** skills are computed, but no truthful **missing-requirements** output exists — and that is a real capability (requirement extraction + required/preferred + evidence + confidence + unknown-handling), **not** the inverse of matched skills (see "What truthful missing-requirement output requires") | `DEC-20260723-001` §5 (source/date/confidence, no false hope) | **Allowed-now** (trust) — sharpest, cleanest first slice |
| 4 | Application Strategy (not auto-apply) | `src/services/apply_service.py`, `src/agent/runtime.py` (idempotent, approval-gated), `src/services/followup_service.py`, `src/services/scheduled_search_service.py`, `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` | No **"best 5/day + why + apply-vs-recruiter"** strategy layer; follow-up exists but isn't strategy-driven | `DEC-20260721-001` stage 2 (daily loop) | **Deferred** (stage 2) — auto-apply stays approval-gated (non-negotiable safety) |
| 5 | Evidence Vault | provenance slices **in active development**: #1364–1368 (attachment/search provenance), #1367 (dedupe with source provenance), `src/services/source_quality.py`, `src/services/job_link_trust.py`; #1336 track | No **CV-claim → evidence** linkage (clickable origin per achievement) | `DEC-20260723-001` §5 (no invented claims) | **Allowed-now** (trust) — but do **not** collide with the in-flight #1336 provenance work |
| 6 | Recruiter Mode | none found (targeted search) | Entire capability absent | `DEC-20260721-001` stage 5 (employer side LATER) | **Deferred** (stage 5) |
| 7 | Outcome Learning | `src/services/career_memory.py` records decisions; `application_board.py` tracks lifecycle | No **learning loop** that reads outcomes and adjusts title/CV/platform strategy | `DEC-20260721-001` stage 2–3 (learn from accept/skip/reject → data moat) | **Deferred** (stage 2–3) |

---

## What this means

- **Do NOT open a broad `competitive-features` branch that re-implements
  `career_memory.py`, `job_match_explanation.py`, `eligibility_filter.py`, or the
  provenance layer.** They exist and/or are in active development (#1336,
  #1364–1368). Rebuilding them would duplicate code, collide with the live
  provenance track, and violate "no new features" + "one writer per objective" +
  "do not reintroduce parallel implementations."
- **Three proposals are the trust engine, not "new features"** — #1 (grounded
  memory), #3 (explainable/honest matching), #5 (evidence-backed claims). These
  are explicitly named as the moat in `DEC-20260723-001` and are allowed under the
  lock as reliability work.
- **Four proposals are genuinely staged for later** — #2 (full UAE engine, stage
  3), #4 (application strategy, stage 2), #6 (recruiter, stage 5), #7 (outcome
  learning, stage 2–3). They wait for their stage or explicit owner override of
  the lock.

---

## Recommended first slice (when the owner greenlights a build)

**Explainable matching — surface the *missing requirements* + honest verdict**
(proposal #3). Rationale:

- **Sharpest real gap:** `build_match_explanation` already returns
  verdict/confidence/summary/next_step and computes *matched* skills, but it does
  **not** produce a truthful missing-requirements output. **This is not simply
  "the inverse of matched skills."** A skill absent from the profile's skills
  array is not evidence the candidate lacks it — the requirement may be unstated,
  the evidence may live in CV prose the skills array never captured, or the item
  may be "preferred," not "required." A trustworthy missing-requirements feature
  is a real capability to design, not a set-subtraction — see the requirements
  below. This is why it is a *recommended* slice, not a trivial one.
- **Purely trust-aligned:** directly implements `DEC-20260723-001` §5 (honest,
  no false hope) — allowed under the lock as reliability work, not a new feature.
- **Low blast radius / no overlap:** it extends one existing service; it does not
  touch the in-flight #1336 provenance track, billing, auth, or the landing page.
- **Highest differentiation per line:** the honesty line — *"Apply, but do not
  rewrite your CV to claim ADNOC approval / Arabic / an Abu Dhabi driving
  licence"* — is exactly what Huntr/Teal do **not** do, and it reinforces the
  trust moat rather than fighting it.

#### What truthful missing-requirement output requires (not set-subtraction)

Any implementation of the missing-requirements verdict must produce, per surfaced
requirement:

- **Requirement extraction from the job text** — parse the actual posting body
  for stated requirements, rather than diffing two skills arrays.
- **Required-vs-preferred classification** — distinguish hard requirements from
  "preferred / nice-to-have," because the honest verdict differs for each.
- **Evidence comparison against the user's profile and CV** — check the full CV
  text/structured evidence, not only the profile `skills` array, before deciding
  a requirement is unmet.
- **Source text and confidence** — cite the requirement's source span and attach
  a confidence level (`DEC-20260723-001` §5: source/date/confidence).
- **Unknown / unverified handling** — an explicit "unknown" state when the job
  text is silent or the profile has no signal either way; never collapse unknown
  into "missing."
- **No negative inference from absence** — the system must **not** conclude the
  candidate lacks a requirement merely because it was not found in the profile.
  Absence of evidence is not evidence of absence.

Until those exist, the honest verdict for an unconfirmed requirement is "we
couldn't verify this," not "you're missing this."

That slice, if taken, must still go through the normal gate: Plan Mode →
smallest-safe single-PR → focused tests → owner approval. It is **not** authorized
by this document.

### Product-generalization note (required)
Every item above must be **global and user-agnostic** (`CLAUDE.md` Product
Generalization Rule): the missing-requirements/verdict logic must cover a
complete-profile user, a no-CV user, a guest session, Arabic and English input,
and multiple unrelated target roles — never one account or one saved role list.

---

## Verification note (faithful)

Claims of "already exists" were confirmed by reading the cited modules. Claims of
"no dedicated module" (salary-sanity, driving-licence, misleading-title, recruiter
outreach, outcome-learning loop) come from a **targeted** grep over `src/`, not an
exhaustive audit — confirm absence before building any of them.

## Cross-references

- `AI_WORKSPACE/CAREER_OS_VISION.md` — the owner's 10-layer Career OS (this
  proposal is a refinement, not a replacement).
- `AI_WORKSPACE/DECISIONS.md` → `DEC-20260723-001` (trust-first lock),
  `DEC-20260721-001` (five-stage order).
- `AI_WORKSPACE/PROJECT_STATUS.md` — current execution lock + #1336 status.
- `AI_WORKSPACE/RICO_INTELLIGENCE_PHASE1.md`, `CAREER_CONTEXT_PROGRAM.md` — live
  intelligence/context tracks to coordinate with, not duplicate.
