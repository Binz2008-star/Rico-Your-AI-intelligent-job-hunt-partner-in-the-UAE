# Rico — Launch Film (`/explainer`)

A self-playing, self-contained 60-second launch film for Rico. No build step,
no framework, no npm deps — plain HTML/CSS/vanilla JS. Served statically by
Vercel from `apps/web/public/explainer/`.

## Files

| File | Role |
|------|------|
| `index.html` | **Chooser** (`/explainer`). Every load draws the next film from a randomized non-repeating cycle (option-2 / option-3 / option-3b, all three before any repeat — deck persisted in `localStorage`) and navigates to it tagged `#rico-rotation`; the film masks its address bar back to the chooser (`history.replaceState`), so reloads re-enter the rotation. After a film's single pass the visitor lands on `/?after-film=1` (landing page). Regression suite: `apps/web/__tests__/explainer-film-rotation.test.ts`. |
| `option-1.html` | **LOCKED** signature cut. Approved by the owner — do **not** change without explicit owner sign-off. |
| `option-2.html` | **Working copy** (identical to Option 1 today). All pending tweaks land here first, then get locked/promoted when approved. |
| `shot_1.mp4` … `shot_10.mp4` | Optional self-hosted clips (see "Clips" below). Not committed yet. |

> When the owner picks a winner, promote it by copying that option over the
> file the site links to (or repoint the site CTA). Keep the loser for history.

## How the film works (inside `option-*.html`)

- **Scenes**: 10 `<section class="scene" data-src="shot_N.mp4">` blocks → 7
  narrative beats. Timing is the `DUR` array (ms) in the script; it sums to
  60000. To add/remove a scene, edit both the DOM and `DUR`.
- **Clips**: sourced through the `CLIPS` map at the top of the script (keyed by
  `data-src`). Falls back to the literal filename if a key is missing, and to an
  animated CSS placeholder if the file/URL can't load.
- **Bilingual EN/عربي**: every caption/label carries `data-en` + `data-ar`.
  `applyLang('en'|'ar')` swaps text, flips `<body dir>`, and switches fonts
  (Amiri + Noto Sans Arabic). Headlines/kickers/subs word-stagger; everything
  else is a plain text swap. Use `~` in a caption string for a line break.
- **Cuts**: bottom-centre switcher — Cinematic (UI overlays), Footage (film
  only), Bold (huge type). Body class `cut-a|b|c`.
- **Sound**: a procedural Web Audio score (no audio file). Starts on the sound
  toggle (browsers block autoplay audio). Swell hook in `audioScene(i)`.
- **Skip / CTA**: both go to `REGISTER_URL` (one constant near the top of the
  script). Currently the Jotform waitlist. Change to `/signup` when open
  registration launches.

## Clips (Higgsfield)

Generated with Higgsfield `kling3_0_turbo`, 16:9, 720p, 5s each, brand-locked
prompts (near-black, gold `#C9A84C`, teal `#01696f`, no purple, no on-screen
text). The `CLIPS` map currently points at Higgsfield CDN URLs.

**For production permanence, self-host:** download each mp4 from the Higgsfield
generations and drop them here as `shot_1.mp4` … `shot_10.mp4`, then clear the
`CLIPS` map (or set each value back to `'shot_N.mp4'`). The loader falls back to
the local filename automatically.

Scene → shot mapping: 1→shot_1 (problem/opener), 2→shot_2 (overwhelm),
3→shot_3 (meet Rico), 4→shot_4 (CV read), 5→shot_5 (match grid),
6→shot_6 (auto-apply), 7→shot_7 (timer), 8→shot_8 (pipeline),
9→shot_9 (Dubai cityscape), 10→shot_10 (particle CTA).

## Continuing this work

- Apply new tweaks to **`option-2.html`** only; leave `option-1.html` frozen.
- Keep changes framework-free and self-contained (this file must run by just
  opening it). Animate only `transform`/`opacity`; respect
  `prefers-reduced-motion`.
- Verify by opening the file in a browser (or headless Chromium). The sandbox
  proxy blocks the Higgsfield CDN, so locally you'll see placeholders — that's
  expected; real footage plays on the deployed preview.
- **Pending:** owner's "tweak #3" — slogan/text revisions (EN + AR). Update the
  relevant `data-en`/`data-ar` pairs when the copy arrives.

See `AI_WORKSPACE/HANDOFFS/2026-07-12-rico-launch-film.md` for the full handoff.
