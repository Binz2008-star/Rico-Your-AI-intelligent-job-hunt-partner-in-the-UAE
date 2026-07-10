# Audit — Career Terminology & Domain Lexicon (Arabic/English)

**Date:** 2026-07-10
**Author:** Rico AI agent session (branch `claude/career-terminology-audit-ojq1xl`)
**Status:** Read-only audit. No code, no prompt/provider/routing changes, no extraction-logic changes.
**Scope note:** This audit does not touch #920 (unrelated `/privacy` & `/refund-policy` legal-review
thread) or any frontend test-health / CI-gate work. Both are separate, unrelated efforts.

---

## Why this audit exists

Rico currently localizes Arabic/English by pairing hand-written UI strings (`translations.ts`) and by
writing English-first regex/keyword logic in the backend, with Arabic patterns added ad hoc where a
maintainer noticed the gap. There is **no single bilingual domain lexicon** — no place that says, once,
"these are the accepted English and Arabic terms, synonyms, and aliases for X concept in a UAE/GCC
career context." This audit maps what exists today, what's missing, and where a lexicon layer would
plug in — without proposing prompt, provider, or extraction-code changes yet.

---

## 1. What exists today

### 1.1 UI translations — `apps/web/lib/translations.ts` (2,207 lines)

- Structured as two parallel blocks: an `en` object and an `ar` object, each a flat `key: "string"` map
  covering landing, chat/command, onboarding, profile, jobs, applications, and settings surfaces.
- Bilingual coverage is broad and appears actively maintained (`feat(landing): add verified Arabic RTL
  localization`, `a696ee8`, merged 2026-07-10 — same day as this audit).
- Domain acronyms (**HSE**, **ESG**) are kept in Latin script inside Arabic strings rather than
  transliterated or translated, e.g.:
  - `apps/web/lib/translations.ts:1159` — `"مفصولة بفواصل، مثل: HSE، ESG، الاستدامة"`
  - `apps/web/lib/translations.ts:2077` — `"مثال: مدير HSE، مدير العمليات"`
  This matches real UAE/GCC professional usage (HSE/QHSE/ESG are used in English even in Arabic CVs and
  job ads) — it is a **correct existing pattern**, but it is incidental, not a documented rule any
  future contributor can rely on.
- "CV" and "resume" are already used as interchangeable synonyms in user-facing copy, e.g.
  `cmdCvWrongType` (`translations.ts:733`): *"This document does not look like a CV or resume."* — good
  practice, but the synonym pairing exists only inside that one string, not as a reusable concept.
- "Salary" and "Compensation" both appear (`profileSalaryTarget` vs. `landingMemoryCompensation`) as
  independent word choices in different surfaces, not a declared synonym pair.
- "Match" is the only surfaced term for fit/suitability (`matchThresholds`, `highMatchOnly`, `cmdMatch`,
  `jobsFilterHigh: "85%+ match"`). "Fit" / "suitability" do not appear — consistent today, but there is
  no glossary entry recording that "match" was the deliberate choice.

**Conclusion:** `translations.ts` is a **UI string table**, not a domain lexicon. It has no synonym
graph, no alias list, and no per-term register/notes field. Consistency currently survives on developer
memory, not on an enforced source of truth.

### 1.2 Backend Arabic/intent handling

- `src/rico_chat_api.py` (~20k lines) is English-first: Arabic detection is a single boolean gate
  (`_is_arabic_text`, line 4039) that flips which pre-written string branch is used — it is not a
  translation or lexicon layer.
- Arabic job-search phrasing **is** reasonably well covered by hand-written regex, e.g.:
  - `وظائف|فرص عمل` (jobs / job opportunities) — `rico_chat_api.py:812`
  - `الوظائف المحفوظة` (saved jobs) — `rico_chat_api.py:619-621`
  - `راتبي المتوقع` (my expected salary) — `rico_chat_api.py:671`
  But each pattern is authored independently, scattered across dozens of separate regexes, with no
  shared term list behind them. There is no Arabic equivalent for "شاغر" (vacancy) or "منصب" (position)
  alongside "وظيفة"/"فرصة" — a partial synonym gap on the Arabic side that mirrors the English side's
  richer job/role/vacancy/opening coverage.
- `src/rico_intent_router.py`:
  - `_INDUSTRY_RE` (line 173-176) is an English-only hardcoded regex covering `hse, ehs, qhse, esg,
    sustainability, environment(al), oil & gas, construction, banking, finance, fintech, tech(nology),
    healthcare, hospitality, retail, logistics, real estate`. **No "medical" (only "healthcare"), no
    "legal", no "engineering"** as their own matched industry terms.
  - `_TITLE_PHRASES` (line 190-197) is a fixed list of ~16 English job titles (`hse manager`, `qhse
    manager`, `software engineer`, `finance manager`, etc.) with **no Arabic titles at all** and no
    banking/medical/legal-specific titles beyond the generic set.
  - `_SALARY_RE` and `_EXPERIENCE_RE` are English-pattern-only (`aed|usd|gbp|eur`, `years?|yrs?`); Arabic
    numerals/phrasing for salary or years of experience are not matched.

### 1.3 CV/profile extraction terms — `src/cv_parser.py`

- `COMMON_SKILLS` (line 40-45) is a **flat English keyword list**: `hse, qhse, ehs, safety, risk
  assessment, iso 9001/14001/45001, audit, compliance, esg, sustainability, environmental management,
  incident investigation, marketing, seo, ...`. No synonyms, no aliases, no Arabic terms.
  - An Arabic-only CV describing "الصحة والسلامة والبيئة" (health, safety & environment) or "موارد
    بشرية" (human resources) would not match anything in this list.
  - `LANGUAGE_HINTS` (line 48) does include `"arabic"` as a spoken-language hint, which is unrelated to
    domain-skill extraction.
- `IDENTITY_SIGNALS` (line 54-68) already contains bilingual pairs for identity-document detection
  (e.g. `"passport number"` / `"رقم جواز السفر"`, `"emirates id"` / `"الهوية الإماراتية"`) — this is the
  **one place in the codebase that already does deliberate EN/AR term-pairing for extraction logic**,
  and is a useful existing pattern to point a future lexicon effort at.
- `src/resume_screener.py:395` already has an explicit rule: *"GCC/UAE experience: only if explicitly
  mentioned"* — a defensive, non-inferring design choice worth preserving rather than replacing with
  guesswork once a lexicon exists.
- `src/resume_screener.py:533` matches `visa|work permit|availability|notice period|transferable|noc` —
  English-only notice-period/availability detection.

### 1.4 Application tracking terms

- Status vocabulary (`Applied`, `Mark as Applied`, `Marked Applied`) is consistent in English
  (`translations.ts:694,716-717,787,833,858,937,1085`) and has direct Arabic pairs (`مقدَّم`,
  `تحديد كمتقدّم`, `تم التحديد`, `translations.ts:1786,1808-1809`) — these are professionally phrased,
  not literal word-for-word translations (e.g. "Applied" → "مقدَّم" / "submitted," not a literal
  "applied"-verb calque). This is a second existing example of good practice worth carrying forward.
- "Submitted" and "Tracked" are not surfaced anywhere as user-facing synonyms of "Applied" in either
  language — only "Applied" is used in the UI; "submitted" appears in unrelated contexts (Jotform intake
  form submission), and "tracked" doesn't appear as a status word at all.

### 1.5 Domain-term coverage vs. requested audit list (HSE, QHSE, ESG, Engineering, Medical, Legal, Banking, UAE/GCC)

| Term | English coverage | Arabic coverage | Notes |
|---|---|---|---|
| HSE / QHSE | Strong (CV skills, industry regex, title phrases, UI placeholders) | Kept as English acronym in AR strings (correct GCC convention) | No formal rule documented |
| ESG | Strong (CV skills, industry regex, UI placeholders) | Same as above | — |
| Engineering | Present only via specific titles (`software engineer`, `data engineer`) | None | Not a matched industry category |
| Medical | Only via generic `healthcare` industry match | None | "Medical," "clinical," "nursing" not matched |
| Legal | Absent | Absent | No industry match, no title phrases |
| Banking | Present (`banking`, `finance`, `fintech`) | Absent | — |
| UAE/GCC experience | Explicit, deliberately conservative handling (`resume_screener.py:395`) | Same file, language-agnostic | Good existing pattern |

---

## 2. Missing synonym/alias sets (explicit audit request)

| Concept | Current state |
|---|---|
| job / role / vacancy / opening | English: well covered across many independent regexes in `rico_chat_api.py`. Arabic: covers وظائف/فرص عمل; missing a dedicated match for شاغر (vacancy) / منصب (position). No shared list backs either language — each regex was hand-authored separately. |
| applied / submitted / tracked | Only "Applied"/"مقدَّم" is surfaced to users in either language. "Submitted" and "tracked" are not offered as synonyms anywhere in UI copy. |
| CV / resume / profile | English: "CV" and "resume" already paired in a couple of error strings. Arabic pairing (السيرة الذاتية vs. الملف الشخصي) not confirmed as intentionally distinguished. |
| match / fit / suitability | Only "match" is used, in both languages. No documented decision that this was deliberate. |
| salary / compensation | Both words exist in `translations.ts` in different strings, undocumented as a synonym pair. |
| notice period | English covered (UI + `resume_screener.py` + `rico_chat_api.py`). Arabic UI string for "notice period" specifically (e.g. فترة الإشعار) was not found in this pass — worth explicit verification before any fix is scoped. |
| UAE / GCC experience | Explicitly and conservatively handled in `resume_screener.py` (only when user states it) — the strongest existing example of intentional, non-inferring domain handling in the codebase. |

---

## 3. Recommended source-of-truth location

Create a new top-level workspace directory, **`AI_WORKSPACE/LEXICON/`**, parallel to the existing
`AUDITS/`, `EVALS/`, and `HANDOFFS/` directories, holding a single living file, e.g.
`AI_WORKSPACE/LEXICON/career-terminology-glossary.md`. Recommended shape per entry:

```
term (canonical EN) | canonical AR | EN synonyms/aliases | AR synonyms/aliases |
domain/sector | register notes | consumers (UI copy / search query expansion /
intent classification / CV extraction) | status (proposed / approved)
```

This keeps the lexicon reviewable as a docs PR (GREEN), separate from any code that would consume it
(YELLOW/RED), and gives `MASTER_INDEX.md` a single stable path to reference. Do not fold it into
`translations.ts` — that file is a UI string table keyed for React, not a semantic glossary, and mixing
the two would make the lexicon impossible to reuse from Python backend code.

---

## 4. How this should affect each surface (recommendations only — not scoped for implementation)

- **UI copy** (YELLOW): Once the glossary exists, `translations.ts` entries should cite/derive from it
  for domain terms and status vocabulary, so "Applied," "Salary," "Match," etc. stay consistent as the
  string table grows. No changes proposed now.
- **Search query expansion** (RED): `job_providers.py:334` and `jsearch_client.py` build a single
  literal query string (`f"{role} {location}"`). A lexicon could eventually feed synonym expansion (e.g.
  "HSE Manager" → also search "QHSE Manager", "EHS Manager") — this is search/provider-routing logic and
  is explicitly out of scope for this audit.
- **Intent classification** (RED): `_INDUSTRY_RE`, `_TITLE_PHRASES`, and the scattered job/vacancy
  regexes in `rico_chat_api.py` / `rico_intent_router.py` are prime candidates to eventually be driven
  by the lexicon instead of hardcoded patterns — flagged RED, no extraction/routing changes proposed
  now.
- **CV/profile extraction** (RED): `CVParser.COMMON_SKILLS` is the clearest gap (English-only, no
  aliases) and the highest-value future consumer of a bilingual lexicon — flagged RED, not touched here.
- **Tests/evals** (GREEN): Once a glossary file exists, `AI_WORKSPACE/EVALS/` fixtures should include
  synthetic bilingual CVs/queries per `CLAUDE.md`'s Product Generalization Rule (Arabic input, English
  input, HSE/QHSE/ESG and banking/medical/legal/engineering roles, multiple unrelated target roles) to
  verify lexicon-driven matching once implemented. Adding these fixtures is docs/test-data work and is
  GREEN.

---

## 5. Classification summary

- **GREEN** (safe to do without further approval, docs/glossary/test-fixtures only):
  - Create `AI_WORKSPACE/LEXICON/career-terminology-glossary.md` and populate it from this audit.
  - Add synthetic bilingual CV/query fixtures to `AI_WORKSPACE/EVALS/` once the glossary exists.
  - Document the existing "keep HSE/QHSE/ESG acronyms in Latin script within Arabic strings" convention
    as an explicit rule (currently only a de facto pattern).

- **YELLOW** (UI copy / terminology changes — needs review before touching `translations.ts`):
  - Reconciling "salary" vs. "compensation," diversifying "match" vs. "fit/suitability" if desired,
    surfacing "submitted"/"tracked" as recognized synonyms of "Applied" if product wants that vocabulary.

- **RED** (AI prompt/provider/routing or extraction-logic changes — not to be started without explicit
  owner approval and a separate scoped task):
  - Expanding `CVParser.COMMON_SKILLS` with Arabic terms/aliases.
  - Adding "medical," "legal," "engineering" as first-class matched industries in `_INDUSTRY_RE`.
  - Expanding `_TITLE_PHRASES` with Arabic titles and banking/medical/legal-specific titles.
  - Any query-expansion logic in `job_providers.py` / `jsearch_client.py`.
  - Consolidating the scattered job/vacancy/role regexes in `rico_chat_api.py` behind a shared lexicon.

---

## 6. Explicitly out of scope for this audit

No code changes, no branch beyond this audit document, no PR content beyond this file, no AI
prompt/provider/routing changes, no backend implementation, and no relation to #920 (legal review of
`/privacy` & `/refund-policy` copy) or any frontend test-health/CI-gate work in flight elsewhere.

## 7. Open questions for the owner

1. Should the lexicon be a single bilingual file, or split by domain (HSE/QHSE/ESG, banking, medical,
   legal, engineering) for easier ownership?
2. Should "medical"/"legal"/"engineering" become first-class matched industries, or is current coverage
   (via generic healthcare/title-phrase matches) considered acceptable for now?
3. Priority order for RED-classified follow-up work — extraction (`CVParser.COMMON_SKILLS`) vs. intent
   routing (`_INDUSTRY_RE`/`_TITLE_PHRASES`) vs. search query expansion?
