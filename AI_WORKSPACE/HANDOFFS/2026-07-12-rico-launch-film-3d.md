# Handoff — Rico Launch Film · 3D "Dimensional" cuts (Option 3 / 3B)

**Date:** 2026-07-12
**Branch:** `claude/design-refinement-theming-6889tz` → PR **#996** (draft)
**Head commit:** `e8fe6479` (pushed to origin)
**Owner:** Roben Edwan (Binz2008-star)

## What shipped in this pass

Adds two new self-contained cuts to `apps/web/public/explainer/`, served at
`/explainer`. Framework-free HTML/CSS/vanilla JS, same as Option 1/2.

1. **`option-3.html` — "Dimensional"** — a pure-CSS **3D holographic** film
   (no footage engine like 1/2). Real CSS 3D: `perspective` world, a
   cursor-parallax camera, an orbiting **constellation "model"** (26-node
   fibonacci sphere), words that fly out of depth, a receding 3D card stack of
   ranked roles, and a true-projection starfield. Behind the 3D it composites
   **4 Higgsfield plates** (see below). Same approved bilingual EN/عربي copy
   as Option 2, RTL, procedural Web-Audio score, Skip + CTA.
2. **`option-3b.html` — "Remix"** — footage-forward sibling: plates at higher
   opacity, faster cuts (~41s), bolder type, the constellation demoted to a
   small signature accent. Same copy + plates, re-sequenced.
3. **`index.html` chooser** — now lists all four cuts (1 locked · 2 · 3 · 3B),
   grid switched to `auto-fit`.
4. **Logo lockup fix** — the CTA "R" is now a gold **badge** (rect + knockout
   R) so it no longer reads as a stray "R Rico".
5. **CTA destination** — `REGISTER_URL` on **option-2/3/3b** now points to
   **`https://ricohunt.com/signup`** (owner decision). **Option 1 stays frozen**
   on the Jotform waitlist.
6. **Device pass (3/3b)** — video plates **lazy-load** (only the active scene's
   plate downloads; saves mobile data), constellation/skill-tags/role-stack
   scale down under 640–680px, `muted`+`playsinline` autoplay + reduced-motion
   fallbacks intact.

## Higgsfield plates (kling3_0_turbo video + nano_banana image)

Base: `https://d8j0ntlcm91z4.cloudfront.net/user_3GOb8y64tsMZUlHSHxmAMNWu7Lg/`
- **A · deep space** (video): `hf_20260712_124928_c111475a-4450-4fa6-a45a-9c4ec9e98cce.mp4`
- **B · the core** (video): `hf_20260712_124911_3de76fab-7a56-4c99-81c9-fe70495271f8.mp4`
- **D · gold convergence** (video): `hf_20260712_124913_f2cef411-c9a2-4d76-8a3e-a9211ea9b889.mp4`
- **C · Dubai at night** (image): `hf_20260712_124915_baf6ac3c-30b5-4641-9ab6-ea8727361c4f.png`

Scene→plate map (`PLATE_FOR` in each file): 3 → `A,A,B,B,A,A,C,D`;
3b → `A,A,B,B,D,A,C,D`.

## Open / next

- **Self-host the plates.** They currently point at the Higgsfield CDN (public
  CloudFront, but not guaranteed permanent). Download the 4 assets into
  `/explainer/` and swap the URLs in the `PLATE_SRC` map (loader falls back to
  the ink background). Could not be done in-session (sandbox blocks that CDN).
- **Merge to production** when the owner picks a winner: PR #996 → main deploys
  to `ricohunt.com/explainer/`. Branch also carries the earlier
  pitch/explainer/jotform work — review before merging the whole branch.
- **Higgsfield balance** was ~10 credits after this pass — enough for a couple
  of plate re-rolls if a clip looks weak on the live link.
- Owner intends to **share the film on LinkedIn** to drive signups → the CTA
  now lands on `/signup`.

See `apps/web/public/explainer/README.md` for how the film engine works, and
`2026-07-12-rico-launch-film.md` for the Option 1/2 handoff.
