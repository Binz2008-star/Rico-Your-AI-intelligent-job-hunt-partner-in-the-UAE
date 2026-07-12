# Handoff — Rico Launch Film & design-refinement pass

**Date:** 2026-07-12
**Branch:** `claude/design-refinement-theming-6889tz` → PR **#996** (draft)
**Owner:** Roben Edwan (Binz2008-star)

## What shipped in this pass

1. **Investor prospectus deck** — `apps/web/public/pitch/index.html`, served at
   `/pitch`. Rebuilt in the house "Atelier" system (paper/ink/one hot signal;
   Fraunces · Inter · IBM Plex Mono). Plain, non-technical language.
2. **60-second launch film** — `apps/web/public/explainer/`, served at
   `/explainer`. Cinematic, near-black + gold `#C9A84C` + teal `#01696f`,
   Instrument Serif + Inter (EN) / Amiri + Noto Sans Arabic (AR).
   - Real footage: 10 Higgsfield clips (`kling3_0_turbo`, 16:9). Sourced via the
     `CLIPS` map. Self-host for permanence (see the folder README).
   - Bilingual EN/عربي with RTL, three cuts (Cinematic/Footage/Bold), a
     procedural Web-Audio score + sound toggle, Skip + CTA → `REGISTER_URL`.
   - **Option 1 = locked** (`option-1.html`). **Option 2 = working copy**
     (`option-2.html`) for the next round of changes. `index.html` is the chooser.
3. **Jotform waitlist** (`form.jotform.com/261278237812056`) — trimmed to a
   minimal quick-start (first name, email, mobile/WhatsApp, role, city, optional
   CV, consent); Telegram/salary/"avoid" hidden (data preserved); restyled dark
   gold/teal to match the film; intro rewritten to a deeper, non-chatbot voice.
4. **Backend** — `src/rico_jotform_webhook.py` reads the phone number under
   `phone`/`mobileNumber`/`mobile_number`/`mobile` (41/41 webhook tests pass).

Full technical detail: `apps/web/public/explainer/README.md` and
`docs/WAITLIST_FORM_FIELDS.md`.

## Next / open

- **Tweak #3 (pending from owner):** slogan/text revisions (EN + AR). Apply to
  **`option-2.html`** only — keep Option 1 frozen. Update the matching
  `data-en`/`data-ar` pairs.
- Self-host the 10 clips into `/explainer/shot_N.mp4` and clear the `CLIPS` map
  (the sandbox proxy blocks the Higgsfield CDN, so it couldn't be done here).
- Decide `REGISTER_URL`: currently the Jotform waitlist; switch to `/signup` when
  open registration goes live.
- Optionally rename the Jotform mobile field's unique name to `phone` (backend
  already tolerates `mobileNumber`, so this is cosmetic).

## How to continue (any agent)

Read `apps/web/public/explainer/README.md`. The film is framework-free and runs
by opening the HTML. Keep it self-contained; animate only transform/opacity;
respect reduced-motion. Verify in a browser/headless Chromium (placeholders
locally, real footage on the deployed preview).

## A note from the founder — keep this in mind

The owner is building Rico with real personal investment, and asked that his
words be kept here so whoever continues understands *why* this matters:

> "أشعر بالفخر حيث إنني ألمس نتائج وأراها الآن. الموضوع يهمّني لأنني تعبت، وأودّ
> أن أثبت لنفسي أنني لم أكن أضيّع وقتي على ريكو."
>
> *"I feel proud — I can finally touch and see results. This matters to me
> because I've worked hard, and I want to prove to myself that I wasn't wasting
> my time on Rico."*

Treat this project with care and craft. It's not a throwaway demo — it's
someone's proof to themselves. Ship things that make him proud to show them.

---

## Continuity update — 2026-07-12 17:30 UTC+4

**Branch:** `claude/design-refinement-theming-6889tz`
**Current head:** `e8fe6479d116a22179236d412b568b9985f9824e` (pushed to `origin`)
**PR:** [#996](https://github.com/Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE/pull/996) (draft)
**Vercel preview:** `https://web-git-claude-design-refinement-theming-6889tz-robens-projects.vercel.app`

- Explainer chooser: `/explainer/`
- Dimensional cut: `/explainer/option-3.html`
- Remix / 3B cut: `/explainer/option-3b.html`
- Original working cut: `/explainer/option-2.html`
- Locked cut: `/explainer/option-1.html`
- Investor deck: `/pitch/`

### What changed since the first handoff

- Added **Option 3** (`option-3.html`) and **Option 3B** (`option-3b.html`) 3D cuts.
- **Option 3 + 3B device optimization:** video plates lazy-load on mobile, constellation scales down ~40% on phones, skill-tags and 3D card-stack shrink, muted/playsinline autoplay + `prefers-reduced-motion` fallbacks preserved.
- **CTA fix:** `REGISTER_URL` now points to `https://ricohunt.com/signup` on Option 2, Option 3, and Option 3B. Skip also goes to `/signup`.
- **Option 1 stays frozen** on the Jotform waitlist (no changes).
- **Logo lockup fixed:** the "R" is now a gold badge, no more "R Rico" text lockup.
- Vercel deployment on `e8fe6479` is **Ready**.

### Open before production

- Video plates still load from the Higgsfield CDN. For permanence, self-host the 4 rendered plates (or 10 source clips) into `apps/web/public/explainer/` and update the `CLIPS` map / plate URLs.
- The PR is still **draft**. It needs owner review and explicit approval before marking ready/merge.
- Untracked file at repo root: `rico-ai-pitch-deck.pptx` (44KB). Decide whether to add to `.gitignore`, delete, or commit.

### Next exact action

1. Owner reviews the Vercel preview (especially `/explainer/option-3.html` and `/explainer/option-3b.html`).
2. If the preview is approved, mark PR #996 ready for review and merge.
3. After merge, Vercel deploys to `ricohunt.com` and `/explainer/` becomes the production link.
