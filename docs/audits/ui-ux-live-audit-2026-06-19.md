# UI/UX Recommendations — RicoHunt

**Type:** Live UI/UX audit
**Date:** 2026-06-19
**Method:** Direct live audit of production (`ricohunt.com`)
**Screens covered:** `/command` (Chat), `/flow` (Pipeline), `/profile`, `/upload` (My Files), `/settings`, `/subscription`, and the global sidebar

> Based on direct firsthand observations across all key screens. Recommendations are
> grouped by screen, then prioritized by impact vs. effort in the final table.

---

## 1. Command / Chat Screen — الأعلى أولوية (Highest Priority)

### 1-A. Replace Free-Text Options with Clickable Buttons

**Problem observed:** Rico presents 1/2/3 or A/B/C/D choices as plain text inside the chat
bubble. Users have to type "A" or "1" — and the system misroutes them.
([ricohunt.com/command](https://ricohunt.com/command))

**Fix:** Render every multi-choice response as **inline action buttons** directly below the
message, not as numbered text. One tap = one action. No typing required.

```
┌─────────────────────────────┐
│  Which option sounds best?  │
│  ┌──────────────────────┐   │
│  │ 📄 Draft cover letter │   │
│  │ 🔗 Open job listing   │   │
│  │ 📌 Track it           │   │
│  └──────────────────────┘   │
└─────────────────────────────┘
```

---

### 1-B. Job Cards Need a Real Fit Score Badge

**Problem:** Every card shows the same boilerplate "Role title aligns with your target" — no
percentage, no skill breakdown, nothing differentiating one match from another.
([ricohunt.com/command](https://ricohunt.com/command))

**Fix:** Add a visible **fit score badge** (e.g. `82% match`) on the top-right of each job
card, with a 3-line breakdown on expand: ✅ Matched skills / ⚠️ Gaps / 📍 Location match.

---

### 1-C. "Searching now…" Needs a Hard Timeout Indicator

**Problem:** The spinner runs indefinitely when a search hangs — users have no idea if it's 5
seconds or 5 minutes away. ([ricohunt.com/command](https://ricohunt.com/command))

**Fix:** Add a visible **progress bar or countdown** (e.g. "Searching… 0:12") that resets to
the fallback UI after 30 seconds. The fallback buttons ("Suggest related roles" / "Find jobs
from my CV") are good — they just need to always appear reliably.

---

### 1-D. Sidebar Widgets Don't Load on Page Reload

**Problem:** READINESS and PIPELINE widgets in the sidebar show as blank grey boxes whenever
you navigate back to `/command`. ([ricohunt.com/command](https://ricohunt.com/command))

**Fix:** These should fetch and render on every mount, not just on fresh session load. A
skeleton shimmer while loading is fine — empty grey boxes are not.

---

### 1-E. Cold-Start Warning is Too Subtle

**Problem:** "Rico is waking up — first request after idle can take up to a minute…" appears
as small grey text. Most users won't see it and will assume the product is broken.

**Fix:** Make it a visible **amber banner** at the top of the chat area with an estimated time:
*"⚡ Rico is starting up — your first search may take ~45 seconds."* Dismiss automatically once
the first response arrives.

---

## 2. Pipeline / Application Flow

### 2-A. "Link Opened" is Not a Useful Default Stage

**Problem:** 38 out of 39 tracked items sit at "Link opened" — this stat is noise. It's
auto-populated by any click, including accidental ones.
([ricohunt.com/flow](https://ricohunt.com/flow))

**Fix:** Either remove "Link Opened" as a pipeline stage entirely, or keep it hidden and only
surface it as metadata on the card (timestamp). The visible pipeline stages should start at
**Saved → Applied → Interview → Offer**.

---

### 2-B. Stage Dropdown is Hard to Use

**Problem:** Changing a card's stage requires clicking a small dropdown (`Link opened ▼`) on
the right side of each card — low discoverability, no drag-and-drop.
([ricohunt.com/flow](https://ricohunt.com/flow))

**Fix:** In Board view, enable **drag-and-drop between columns**. In List view, make the stage
badge a larger clickable pill with clear options. The current small dropdown blends into the
dark card background.

---

### 2-C. Stat Cards Show Too Many Zeros

**Problem:** The 9-box stat grid at the top of Pipeline shows: 1 Applied, 0 Follow-up,
0 Interview, 0 Offer, 0 Saved, 38 Link Opened, 0 Opened Externally, 0 Prepared, 0 Rejected,
0 Decision. Eight zeros dominate the screen — cognitively exhausting.
([ricohunt.com/flow](https://ricohunt.com/flow))

**Fix:** Only show stats that are **non-zero** or **meaningful to the current stage**. Collapse
the zero-value boxes or show them as a compact secondary row. Lead with the three that matter:
Applied / Interview / Offer.

---

### 2-D. "Did you apply? Mark it as Applied." Prompt is Buried

**Problem:** The nudge appears as small grey text at the bottom of each card below the date —
easy to miss. ([ricohunt.com/flow](https://ricohunt.com/flow))

**Fix:** Make it a distinct **inline CTA button** ("✓ Mark as Applied") visible immediately
below the job title when status is "Link opened", styled in green/emerald to signal a positive
action.

---

## 3. Profile Page

### 3-A. Completeness Score Mismatch

**Problem:** Sidebar shows 71%, Profile page shows 54%. Two different numbers for the same
concept — one of them is wrong and users lose trust.
([ricohunt.com/flow](https://ricohunt.com/flow))

**Fix:** Single source of truth. Pick one calculation method, display it consistently
everywhere, and show a tooltip explaining what counts toward 100%.

---

### 3-B. Conflict Warnings are Excellent — But Hidden

**Problem:** Rico's smart warnings (excluded keyword "manager" conflicts with target roles,
invalid city, too many target roles) are buried inside the preference form as small orange
text. Most users won't scroll to find them.

**Fix:** Surface **active conflicts as a banner** at the top of the Profile page:

```
⚠️  3 issues may be limiting your search quality  [Fix now →]
```

Clicking expands the list with one-tap fixes.

---

### 3-C. No Visible "Active CV" Indicator on Profile Page

**Problem:** The profile page shows skills and experience but doesn't show which CV is actively
being used for matching — the user has to go to My Files to check.

**Fix:** Add a small "Active CV: [filename]" chip near the top of the Profile page with a
quick-link to My Files.

---

## 4. My Files / CV Upload

### 4-A. CV Role Mismatch Warning Missing

**Problem:** The active CV is a "Technical Product Owner" CV but all job searches target HSE
roles. Rico mentions this in chat but the My Files screen shows no warning at all — the user
could miss it entirely. ([ricohunt.com/flow](https://ricohunt.com/flow))

**Fix:** When the active CV's parsed role doesn't match profile target roles, show a **yellow
banner** on the My Files page: *"⚠️ Your active CV is for a Technical Product Owner role — your
target roles are HSE/Environmental. Consider uploading an HSE-focused CV."*

---

### 4-B. CV Parse Quality Indicators

**Problem:** Cards show "5 skills" and "10 yrs exp" but give no signal about parse confidence.
"30 yrs exp" on the second CV is likely a parse error (career span misread as experience).

**Fix:** Add a **parse confidence indicator** (e.g. "Parsed: Good / Needs review") and a
one-click "Review parsed data" button that shows what Rico extracted from the CV before the
user trusts it.

---

## 5. Settings

### 5-A. Dangerous Profile Fields Need Input Validation

**Problem:** City field accepted "hello" as a valid city — leading to broken searches. Target
roles accepted 8 values with no cap enforced. ([ricohunt.com/flow](https://ricohunt.com/flow))

**Fix:**
- **City:** validate against a UAE city list on input, reject with inline error if not recognized.
- **Target roles:** enforce a maximum of 3–4 with a UI counter ("3/4 roles").
- **Excluded keywords:** warn in real-time if an excluded keyword matches a target role.

---

### 5-B. Fit Score Slider Needs Better Labels

**Problem:** The slider shows "80%" but the label doesn't explain what this means to the user —
they don't know it's hiding 60–79% matches.

**Fix:** Add dynamic guidance text below the slider: *"At 80%, Rico will hide roles that score
60–79% — you may miss relevant matches. Recommended: 60%"*

---

## 6. Global / Cross-Cutting

### 6-A. Dark Theme is Too Dark for a Professional Career Tool

**Problem:** The current near-black `#06060c` background with gold/amber accents looks like a
gaming or entertainment product — not a UAE career platform competing with LinkedIn and Bayt.
([ricohunt.com/command](https://ricohunt.com/command))

**Fix:** Shift to a **deep navy base** (`#0a0e1a`) with indigo accents and clean white cards.
This has been designed in the pending style PR. Referencing current color as the baseline to
move away from.

---

### 6-B. No Empty State Guidance on First Use

**Problem:** A new user landing on `/command` sees the prompt interface with no context about
what they should do first — no onboarding checklist, no "start here" flow.

**Fix:** Add a **first-use checklist** (dismissable) as a sidebar widget or inline card:

```
Get started:
☐ Upload your CV
☐ Set your target roles
☐ Run your first search
```

Auto-dismisses when all 3 are done.

---

### 6-C. No Visual Hierarchy Between "Ask Rico" and Navigation Items

**Problem:** In the sidebar, "Ask Rico" (the primary action) looks visually similar to
"Pipeline", "Applications", "Profile" — same icon size, same font weight. The most important
action doesn't feel primary. ([ricohunt.com/command](https://ricohunt.com/command))

**Fix:** Make "Ask Rico" visually dominant — larger, with a distinct filled button style, not
just a highlighted row. Demote the navigation items to secondary visual weight.

---

### 6-D. "Support on WhatsApp" at Bottom of Sidebar — Wrong Placement

**Problem:** WhatsApp support sits between the user's career navigation and account items,
taking up permanent sidebar space.

**Fix:** Move it to a **floating help icon** (bottom-right corner, `?` or chat icon) that
expands on hover. Free the sidebar for navigation only.

---

## Priority Order

| #  | Recommendation                                      | Impact      | Effort |
|----|-----------------------------------------------------|-------------|--------|
| 1  | Clickable option buttons (replace A/B/C/D typing)   | 🔴 Critical | Low    |
| 2  | Fit score badge on job cards                        | 🔴 Critical | Medium |
| 3  | Sidebar widgets load on every mount                 | 🟠 High     | Low    |
| 4  | "Mark as Applied" as a clear CTA button             | 🟠 High     | Low    |
| 5  | Profile conflict banner at top of page              | 🟠 High     | Low    |
| 6  | Input validation for City + Target roles            | 🟠 High     | Low    |
| 7  | Timeout progress indicator on search                | 🟠 High     | Low    |
| 8  | Completeness score — single source of truth         | 🟠 High     | Low    |
| 9  | Navy/indigo design system (style PR)                | 🟡 Medium   | Medium |
| 10 | Remove "Link Opened" as primary pipeline stage      | 🟡 Medium   | Low    |
| 11 | CV mismatch warning on My Files                     | 🟡 Medium   | Low    |
| 12 | First-use onboarding checklist                      | 🟡 Medium   | Medium |
| 13 | Cold-start amber banner                             | 🟡 Medium   | Low    |
| 14 | WhatsApp support → floating help icon               | 🟡 Low      | Low    |

The biggest UX gain for the least effort is **#1 (clickable buttons instead of typed
options)** — it eliminates BUG-02 entirely from the user's perspective without waiting for the
intent-router fix, and it makes Rico feel like a polished product rather than a terminal.
