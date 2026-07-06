# Dev Handoff — Command/Chat Attachment UX + Signup/Reset Password Parity

> **Type:** Claude Design specification. Describes intended design behavior for a
> future coding task. **No production code. No repo files changed. No build, no
> tests, no PR, no deploy.** Implementation happens in the code repo by the dev.
>
> **Design source:** `Rico Hunt V2.dc.html` (Rico "Aura Intelligence" system).
> **Grounded in the current design's actual behavior** (see §3).

---

## 0. Conversation is the system

> Added after the product-direction review. This is the framing every section
> below serves: Rico is a **full AI career operating system driven by a
> conversation**, not a dashboard that shows cards. The chat is the product;
> cards are supporting UI that appears *inside* the conversation.

**Reflected in the current design (`Rico Hunt V2.dc.html`, `command` → Console):**
Rico opens with a first-person message, states what it knows ("What Rico knows
right now: CV — not uploaded · Profile — partial · Job search — idle"), reads a
CV as a spoken sequence, tags every output by action type, and asks a
clarifying question instead of answering a vague request. These are **design
demonstrations of intended behavior** — not a claim that any engine, parser, or
backend exists.

### What the chat must control
- The chat thread is the **primary surface and single source of flow**. Entering
  the app lands in the conversation; other routes (Jobs, Applications, Profile)
  are **views into state the conversation created**, reachable from chat, never a
  replacement for it.
- The composer is always reachable (attach · text · send). Every meaningful
  product action can be *initiated and understood from the conversation*: find
  jobs, read CV, track/apply, prep interview, edit profile.
- Rico owns **turn-taking**: it interprets intent, decides whether to answer, ask,
  or show a card, and always ends a turn with a clear next step or a question.
- Rico maintains and reflects **session memory** — current CV/profile/job-search
  state — visible in the empty state and the rail ("What Rico remembers").

### Where cards support the chat
- Cards (job match, application status, CV summary, sign-in, saved draft) render
  **as messages inside the thread**, in response to a conversational turn — never
  as a standalone grid that *is* the product.
- The standalone **Jobs** screen is a browsable expansion of the same results, not
  the main experience; job results must also be reachable and explained in chat.
- A card never appears without a conversational reason. Every card is preceded or
  accompanied by Rico saying *why* it's there and *what to do next*.

### How Rico handles missing CV / profile / jobs
- **No CV:** empty state and prompts say so plainly ("CV — not uploaded yet") and
  offer the conversational path ("upload your CV and I'll read your trajectory
  first"). Rico never implies it has read a CV it hasn't.
- **Partial profile:** Rico names the specific gaps ("target role & salary floor
  missing"), and after a CV read calls out missing facts ("notice period and visa
  status") with a choice to add them or proceed — it does not silently guess.
- **No jobs / no matches:** honest, in-voice ("No matches in this range. Try the
  'All' filter, or Rico will surface more in the next scan.") — never an empty
  grid with no explanation.

### How Rico asks follow-up questions
- On a vague or under-specified request, Rico asks **one** focused question
  (role? UAE city? salary floor?) with 2–3 tappable quick answers, rather than
  returning a generic response. Copy stays in Rico's voice, no exclamation marks.
- Follow-ups are single-step and cheap to answer; Rico never interrogates.
- Language of the reply follows the language of the turn (EN / AR / mixed).

### How Rico avoids fake actions — the four action types
Every Rico output that represents an action carries **one** explicit, visible
label so the user always knows its status. In the design these are the tags on
Rico messages:

| Type | Tag (design) | Meaning | Example |
|---|---|---|---|
| Real completed action | **Done** (green) | Rico actually did it in-session | "Tracked to Application Flow", "Saved to target roles" |
| Suggested next action | **Suggested next** (cyan) | A recommendation the user may take | "Recommended next step: open the apply link" |
| Needs confirmation | **Needs your ok** (magenta) | Waiting on user decision/approval | "Two facts are missing — add them, or search now?", drafts to "review before you send" |
| Visual sample / demo | **Sample** (muted) | Illustrative placeholder, not real data | seeded demo cards, example outputs |

- Rico **never** shows "Done" for something it hasn't verifiably completed.
  Opening an apply link is **Needs your ok** ("Rico can't submit for you — tap
  'Mark as applied' once you've sent it"), not a success.
- Drafts (cover letter, follow-up note) are **Needs your ok** — "review before it
  sends" — never auto-sent.
- Image/screenshot attachments are **never** parsed silently; Rico asks to
  confirm the role or link (see §3 Flow B).

### What Claude Code must verify before implementation
- [ ] Chat is the entry surface; Jobs/Applications/Profile read from
      conversation-created state, and job results are reachable + explained in chat.
- [ ] Every card renders inside a thread turn with a conversational reason; no
      card appears without Rico framing it.
- [ ] Missing CV / partial profile / no-matches states are explicit, honest, and
      name the specific gap and next step.
- [ ] Vague input triggers exactly one clarifying question with quick answers, in
      the user's language.
- [ ] Every action output is labelled with exactly one of the four action types;
      the label maps to real backend state, not an assumption.
- [ ] No output labelled "Done" unless the backend confirms completion; apply-link
      and drafts are confirmation/needs-ok, never fake success.
- [ ] Action-type labels are backend-driven (not hardcoded per message in the UI);
      the tag reflects the real result the engine returned.
- [ ] EN / AR / mixed conversation is first-class across all new states.
- [ ] Memory reflected in the UI ("What Rico remembers") is sourced from real
      session/profile state, not static copy, before it ships.

---

## 1. UX goal

- **Attachment UX** — make the command/chat feel natural for attaching a CV or a
  job screenshot/document: attach by click or drag-drop, see a compact file chip
  with filename/type/size/remove, watch honest upload/reading states, and never
  see a faked parse. Unsupported files ask for clarification instead of pretending.
- **Empty/loading states** — make Rico read as an AI career operator, not a
  generic chatbot: every empty and in-progress state explains *why* it's empty
  and *what Rico will do next*.
- **Password parity** — signup and reset match login's show/hide password
  behavior exactly, keyboard-accessible and mobile-safe.

---

## 2. Screens affected

- Command / chat — composer bar, staged-attachment chip, in-thread file bubble,
  drag-drop drop-zone, empty state, thinking/loading state, error/clarification
  replies. *(chat is the `command` route, "Console" variant.)*
- Signup form and Reset-password (set-new-password) form. Login is the reference
  and is **not** redesigned.
- Mobile composer + drawer (narrow widths, keyboard open, safe-area).

Out of scope: dashboard, jobs, profile, billing, backend, chat engine, auth API.

---

## 3. User flows

**Current design behavior (baseline).** In the design today the composer's
attach button immediately posts a hardcoded file bubble and shows a CV summary
after a fixed delay — there is **no staged chip, no filename/size, no remove, no
type check, and success is assumed**. That is the gap this handoff closes.

**Flow A — attach a CV (happy path)**
1. User clicks attach (or drags a file onto the chat card).
2. File is *staged* in the composer as a chip: type glyph · filename · size · ×.
3. User may add a message, then presses Send.
4. On send: a file bubble enters the thread; Rico shows an honest *reading* state
   (hairline progress, "Reading your CV — privately"); then the CV summary card.
5. Summary offers next steps (search matching jobs / set target roles).

**Flow B — attach a job screenshot / document (image)**
1–3. As above, chip shows an image glyph.
4. On send: Rico does **not** claim to have parsed it. It replies asking to
   confirm: "That looks like a job screenshot — tell me the role title or paste
   the posting link and I'll match it against your profile."

**Flow C — unsupported / oversize file**
- At stage time the chip shows an *error* state inline ("Unsupported — use PDF,
  DOCX, TXT or an image, under 5 MB") with a "Choose another" action. Send stays
  disabled; nothing is posted to the thread until it's resolved.

**Flow D — remove before send**
- The chip's × clears the attachment and returns the composer to text-only.

**Flow E — signup / reset password**
- Password fields render masked; an eye toggle reveals/hides; confirm-password
  has its own toggle; inline error text on mismatch/weak; submit posts.

---

## 4. Desktop behavior

- Composer is one glass row: `[attach] [text input, flex] [send]`. When a file is
  staged, the **chip sits on its own line directly above** the input row, full
  composer width.
- Drag-over the chat card shows a **dashed cyan drop-outline** overlay (reuse the
  upload page's dashed-border treatment); dropping stages the file.
- Send is enabled when there is text **or** a staged, supported file; a staged
  *error* file keeps send disabled with a quiet reason.
- Password toggle is a trailing icon-button inside each password field; input
  keeps right padding so revealed text never sits under the icon. Toggling holds
  caret position and never submits.

---

## 5. Mobile behavior

- Composer stays bottom-docked, always reachable, above the keyboard, never
  overlapping the last message; respect `env(safe-area-inset-bottom)` (already
  used in the design's composer padding).
- Staged chip appears above the input and remains visible with the keyboard open.
- Attach and send targets ≥44×44px with clear spacing.
- **Long filenames** truncate with a middle ellipsis (keep the extension visible);
  the chip never pushes the × off-screen or forces horizontal scroll.
- No nested-scroll trap: the thread scrolls; the page behind the composer does not
  fight it.
- Quick-action chips row scrolls horizontally; it must not steal vertical scroll.
- Password toggle ≥44px; doesn't collide with the OS keyboard's own reveal.

---

## 6. Arabic / English behavior

- Chat already flips message direction per message (Arabic → RTL bubble, right
  alignment). Keep that for file bubbles and clarification replies.
- **Attachment chip under RTL:** labels follow document direction, but the
  **filename stays LTR-isolated** (bidi isolation) so `CV_2026.pdf` isn't visually
  reordered; the extension and size read correctly.
- Composer input direction follows the typed language; attach/send keep a stable,
  mirror-aware position (attach leading, send trailing).
- Clarification / empty-state copy exists in EN and AR; no exclamation marks,
  Rico voice ("Send a text-based CV" not "Oops!").
- Password toggle is icon-only and direction-agnostic; lands on the trailing edge
  of the field in both LTR and RTL. All new strings go through the translation
  layer, not hardcoded.

---

## 7. Accessibility notes

- Attach control has an explicit `aria-label` ("Attach CV or job document").
- When a file stages, announce it to assistive tech via a live region
  ("CV attached, ready to send" → "Reading CV" → "CV read").
- Chip state uses **icon + text, not color alone**; progress exposes a
  `role="progressbar"` equivalent.
- Remove (×) is keyboard-reachable and labelled ("Remove attached file").
- The button-triggered file picker is always available — drag-drop is never the
  only path.
- Password toggle: `aria-label` reflects the action ("Show password" / "Hide
  password"), `aria-pressed` reflects state, keyboard-operable, `:focus-visible`
  ring (the design system already defines a cyan focus ring).

---

## 8. Empty / loading / error states (chat)

| State | Copy intent (Rico voice) |
|---|---|
| No CV uploaded (empty thread) | Command-center intro + suggestion rows (exists). Add: quiet "No CV yet — upload one and I'll read your trajectory." |
| CV staged, not sent | Chip shows filename/size, send ready. |
| CV reading (post-send) | Hairline progress, "Reading your CV — privately." No result claimed yet. |
| Job search in progress | "Rico is working the scoring loop…" (exists — keep). |
| No matching jobs | "No matches in this range. Try the 'All' filter, or Rico will surface more in the next scan." (add) |
| Application saved / tracked | In-chat status card with next step (exists — keep). |
| Upload failed / unsupported | Chip error + a Rico clarification, never a fake success (add). |
| Vague / generic request | Rico asks one clarifying question (role? city? salary floor?) instead of a generic answer (add). |
| Arabic / mixed input | Reply in the user's language, RTL where Arabic (exists — extend to new states). |

---

## 9. Attachment states (chip state machine)

`empty → staged → (sending) → reading → done`
`staged → error(unsupported/oversize) → (choose another) → staged`
`staged → removed → empty`

Per-state chip anatomy: **type glyph · filename (middle-ellipsis) · size · state
indicator · remove ×**.
- `staged` — neutral glass chip, cyan type glyph, × enabled, send enabled.
- `error` — magenta accent, short reason, "Choose another"; send disabled.
- `reading` — hairline cyan progress on the chip or as the in-thread reading card.
- `done` — file becomes a thread bubble; composer returns to empty.

Supported: PDF, DOC/DOCX, TXT (CV path) and PNG/JPG/WEBP (job-screenshot path).
Limit: **5 MB** (matches the design's existing upload copy). The real limit value
should be read from backend config, not hardcoded in the UI (see §11).

---

## 10. Auth password-visibility parity states

| Field | Default | Toggle | Notes |
|---|---|---|---|
| Signup · password | masked | eye show/hide | mirrors login exactly |
| Signup · confirm password | masked | independent eye | error text on mismatch |
| Reset · new password | masked | eye show/hide | |
| Reset · confirm new password | masked | independent eye | error text on mismatch |

- Each toggle: `aria-label` + `aria-pressed`, keyboard-operable, ≥44px, never
  moves focus / clears the field / submits the form.
- Error text is inline, specific, calm ("Passwords don't match", "Use at least 8
  characters") — no assumptions about backend auth rules beyond what login shows.
- Signup also carries the same maintenance-mode framing login already has.

---

## 11. Developer implementation notes (guidance, not code)

- **Password parity already has a reference** in the login form (toggle with
  `aria-label` + `aria-pressed`). Lift that same pattern into signup + reset — a
  *parity* task, not a new invention.
- **Attachment state is composer-local** (staged file, progress, result), distinct
  from the message list. The staged chip is pre-send; the file bubble is the
  post-send record. Don't post to the thread until send.
- **File limit + accepted types are backend/config-owned.** Show the constraint,
  but read the real number from existing config so copy can't drift from
  enforcement.
- **Never assert a successful parse** the UI can't verify — show a reading state,
  then a result the backend actually returned; for images, ask to confirm.
- **Reuse existing primitives:** glass card, hairline cyan progress track, status
  node, pill/chip, dashed drop-outline (upload page) — no new component vocabulary.
- Route all new strings through the translation layer (EN + AR).
- Do **not** touch the chat engine, upload endpoint, CV parser, or auth API.

---

## 12. Scope boundaries

**In scope:** composer attach affordance + staged chip + state machine +
drop-zone + mobile composer spacing; new/expanded chat empty/loading/error
states; signup + reset password toggles and signup maintenance framing.

**Out of scope / forbidden as a first change:** backend, chat engine, upload
endpoint, CV parser, auth/session/login redesign, billing, jobs, profile,
routing; framework upgrade; global CSS rewrite; Telegram automation; all-in-one
redesign.

---

## 13. Acceptance checklist

**Attachment UX**
- [ ] Attach by click and by drag-drop; drop-zone outline on drag-over.
- [ ] Staged chip shows type · filename (middle-ellipsis) · size · removable ×.
- [ ] Accepted types + 5 MB limit shown proactively (value from config).
- [ ] States render by icon+text not color alone: staged / error / reading / done.
- [ ] Send gated: enabled on text or a supported staged file; disabled on error.
- [ ] Unsupported/oversize → chip error + Rico clarification; nothing faked.
- [ ] Image attach → Rico asks to confirm role/link; no fake parse.
- [ ] Mobile: composer reachable, above keyboard, no overlap, ≥44px, safe-area,
      long filename truncates, no nested-scroll trap.
- [ ] RTL: chip + copy mirror; filename stays LTR-isolated.

**Chat states**
- [ ] No-CV, no-matches, upload-failed, and vague-request states all present and
      in Rico voice; Arabic/mixed replies in-language.

**Password parity**
- [ ] Signup + reset password and confirm-password fields masked by default with
      independent eye toggles.
- [ ] Toggles: `aria-label` + `aria-pressed`, keyboard, ≥44px, no focus loss / no
      submit / no field clear.
- [ ] Inline error text on mismatch/weak; signup maintenance framing at parity.
- [ ] New strings in translation layer (EN + AR), none hardcoded.

**Both**
- [ ] No backend / engine / parser / auth-API files touched.
- [ ] Only existing Rico design primitives used.

---

## 14. Risks / follow-ups

- **Honesty risk (highest):** the current design assumes parse success. If the
  build keeps assuming success while the backend can fail, the UI will lie during
  outages — the reading→result split and the image-clarification path exist to
  prevent that. Treat "no fake success" as a hard requirement.
- **Config drift:** hardcoding the 5 MB limit / accepted types in the UI will
  eventually mismatch backend enforcement — bind to config.
- **RTL bidi:** filenames and mixed EN/AR lines are the most likely place for
  visual reordering bugs; test with a real Arabic CV filename.
- **Auth-state source:** the design fakes auth with a boolean; the real app has
  two auth-state sources (per the Phase 0 audit) — reconcile before wiring signup
  UI to live state, so the toggle work isn't redone.
- **Mobile keyboard:** short-height devices (iPhone SE, Galaxy Fold narrow) are
  where composer overlap regresses; include them in QA.
- **Follow-up (not this task):** a full RTL page-mirroring pass and consolidating
  the two auth-state sources are separate, larger efforts to roadmap.

---

*End of design handoff. Specification only — it modifies no repository and asserts
nothing about builds, tests, or PRs.*
