# Design-handoff `incoming/` audit — 2026-07-24

Scope: `design-handoffs/incoming/`. Evidence-backed inventory + gap analysis.
**No code changes, no PR (until this one), no deletion, no deployment were
made.** The one exception is the quarantine action in §1, which is a
filesystem move outside the repository, not a code change. **No executable
file was run, opened, or launched at any point in this audit** — this
includes the quarantined `.exe` and every video/audio file discussed in §5;
all video/audio findings are limited to filesystem-level container
inspection (`file`, `ls`), never playback or execution.

### Evidence provenance — read before trusting a claim below

This audit draws on two categories of evidence with very different trust
levels, and every finding below is one or the other:

- **`[LOCAL-FS]`** — verified by inspecting files on the machine that ran
  this audit (sizes, hashes, `file` output, zip listings, image contents).
  `design-handoffs/incoming/` is **untracked by Git** (confirmed via
  `git status`), so essentially all of §1, §2, §3's "reference pack" side,
  and §5 falls in this category — it describes what exists on disk, not
  what exists in the repository's history.
- **`[REPO]`** — verified by reading tracked files in this Git repository
  (cited as `path:line`), i.e. claims about what is actually live/shipping.
  §3's "live billing" side, §4's "live homepage" side, and the
  `COMMAND_V5_IMPLEMENTATION_MAP.md` references throughout are this
  category.

Where a table or paragraph mixes both, the category is called out inline.

---

## 1. Quarantine record — unexpected executable `[LOCAL-FS]`

Every fact in this section is filesystem/Git-metadata inspection on the
machine that ran this audit; `design-handoffs/incoming/` is untracked, so
none of it is a repository claim.

| Field | Value |
| --- | --- |
| Original path | `design-handoffs/incoming/kimi_3.1.3--downloadid-0c5ebb0069645347f99c2d08a31a9e5c26.exe` |
| Size | 444,625,216 bytes (~424 MiB) |
| SHA-256 | `C58C16450DB16E686BA01592D34110DEBBF1D0FAE2D0465CF7C06558AF97EE5B` |
| Created / modified (filesystem) | 2026-07-23 02:19:56 / 02:23:19 |
| Git tracking state | **Untracked** (`git status --porcelain` → `??`); not present in `git ls-files` |
| Git history | **None** — `git log --all --diff-filter=A -- <path>` and `git log --all -- <path>` both return empty. Never committed, on any branch, at any point. |
| `.gitignore` | Not matched by any ignore rule (`git check-ignore` returns nothing) — it simply had never been staged |
| Action taken | Moved (not copied, not executed, not opened) to a non-repository quarantine directory on the local machine that ran this audit (exact path omitted here as machine-specific; available to the owner on request). Confirmed absent from the repo tree and from `git status` afterward. |
| Deletion | **Not deleted.** Awaiting owner decision. |

Assessment: zero repo/supply-chain exposure (never tracked, never in history), but it should not have been sitting in a design-assets folder. Recommend permanent deletion once you confirm you don't need it, since nothing in the design program references it and it doesn't match any `.dc.html` / handoff asset naming convention.

---

## 2. Structured inventory `[mixed — see column note]`

Every column except **Repo evidence** is `[LOCAL-FS]` (the `incoming/` files
themselves are untracked). The **Repo evidence** column is `[REPO]` wherever
it cites a `path:line`, and `[LOCAL-FS]` wherever it only describes the
zip/file contents (e.g. reading a `.md` file that itself lives inside an
untracked zip).

Legend for **Status**: `LIVE` = implemented and shipping · `PARTIAL` = shipped in a different form · `NOT PORTED` = deliberately not ported (owner/eng decision) · `UNSHIPPED` = no implementation, no decision on record · `REFERENCE ONLY` = historical design-process artifact, not meant to ship · `MISLABELED` = wrong file extension/content mismatch.

### 2.1 Command Workspace v4/v5 — design references (the active program)

| Path | Type / size | Duplicate group | Intended surface | Status | Repo evidence |
| --- | --- | --- | --- | --- | --- |
| `تطبيق التصميم على النظام.zip` → `design_handoff_rico_command_workspace/*.dc.html` (6 files, v1–v4) + `HANDOFF-rico-command-workspace-v4.md` + `docs/DEC-20260717-001.md`, `docs/DEC-20260718-001-audit.md` | zip, 4.0 MB | `تطبيق التصميم على النظام1.zip` is a 9-file subset of the same content (byte-identical `.dc.html`/`.md` files by name+size) | `/dashboard`, `/command`, `/applications`, `/upload`, `/profile` (Career OS "v4" concept) | **PARTIAL / SUPERSEDED** | `AI_WORKSPACE/COMMAND_V5_IMPLEMENTATION_MAP.md:9` records that v4 was explicitly superseded 2026-07-21 by the v5 artifact below. v4's Career OS ideas (goal panel, Career Health row, Ask Rico copilot, trust vocabulary) partially live in `DashboardAtelier.tsx`, `ChatActionCard.tsx` — verified in §2.1 findings from the earlier chat-review this session. |
| `2026-07-21-command-workspace-artifact/Rico_Command_Workspace_v5.dc.html` | html, 215 KB, 2071 lines | none found | Same 5 modes, v5 visual system | **PARTIAL — this IS the sole current source of truth** | `COMMAND_V5_IMPLEMENTATION_MAP.md:9-18` names this exact path as "the sole visual source of truth" for the still-in-progress v5 program. PR1–4 merged (`#1242`,`#1243`,`#1271`,`#1275`); PR5 motion/final-QA formally unscheduled until this session's `#1356`/`#1357` (hover-lift physics + Upload entrance motion — done this session, not yet reflected in the map's PR ladder table). |
| `rico-chat-design.html` | html, 49 KB | none | `/command` chat, "Atelier warm" direction | **REFERENCE ONLY (superseded by v5)** | `DEC-20260717-001.md` (inside the Arabic zip) names this exact design decision — "Atelier warm" won over "Obsidian" and "Nocturne" candidates for `/command` on 2026-07-17. The v5 artifact above supersedes it program-wide. `LandingPageNocturne.tsx` in the live repo confirms "Nocturne" existed as a real candidate/experiment, consistent with the decision doc. |
| `atelier-reference-pack.zip` (32 MB) → `pr1-tokens-theme-i18n`, `pr2-landing-pricing`, `pr3-dashboard-shell`, `pr4-support-legal-auth`, `pr5-rico`, `pr6-visual-qa` | zip | `pr5-rico.zip` (3,084,991 B) and `pr6-visual-qa.zip` (12,851,612 B) also exist as **top-level duplicate files** in `incoming/`, byte-size-identical to the nested copies | Full alternate implementation — tokens, landing, pricing, dashboard shell, auth/legal, `/rico`, visual QA | **PARTIAL — origin of current "Atelier" naming, NOT current stack** | `atelier-reference-pack/README.md` states source = `Lovable prototype "lovable/design-preview-handoff"`, a **TanStack Start + Vite + Supabase** app — a different stack from the live Next.js/FastAPI/Neon/Paddle repo. `DEC-20260718-001-audit.md` (read in full) explicitly labels this whole pool "Design intent only... does NOT reflect the shipped app runtime" and marks nearly every route path "[UNVERIFIED — needs code inspection pass]". The "Atelier" naming (`DashboardAtelier.tsx`, `atelier-kit/`, etc.) visibly traces back to this pack, so PR1 (tokens) and PR3 (dashboard shell) ideas are the ones that most plausibly influenced what shipped — but **not verified line-for-line**, and PR2 (landing/pricing), PR4 (auth/legal/support), PR5 (`/rico`) show no equivalent live routes. See §3 and §4 for the two sub-packs actually compared against live code. |
| `Remix of Career Compass AI.zip` (16.8 MB) | zip | none | The actual TanStack Start prototype app referenced as "Pool B" in `DEC-20260718-001-audit.md` | **REFERENCE ONLY** | Confirmed via top-level listing: `.lovable/plan.md`, `AGENTS.md`, `DESIGN-HANDOFF.md`, `HANDOFF_TO_CLAUDE.md`, `design-handoff/*`, `bun.lock` — this is a full separate TanStack/Bun project, not Next.js. `DEC-20260718-001-audit.md` explicitly says this pool was read-only reference and "I will not modify any file in Pool B." Not a source to port from directly into the FastAPI/Next.js repo without a full rewrite. |

### 2.2 Brand / marketing concept — "Your Career, in Motion"

| Path | Type / size | Duplicate group | Intended surface | Status | Repo evidence |
| --- | --- | --- | --- | --- | --- |
| `landing-hero.png` (5.68 MB), `desktop-en.png` (7.22 MB), `arabic-desktop.png` (6.95 MB), `arabic-mobile.png` (5.68 MB), `dark-bg.png` (6.64 MB), `mobile-en.png` (7.26 MB) | png, full-scene marketing comps | Each has a byte-size-identical `hf_2026072*_*.png` twin (Higgsfield raw export saved alongside the curated name) — see §2.4 | Public landing hero / marketing collateral | **UNSHIPPED** | No route, component, or copy string from these comps (`"YOUR CAREER, IN MOTION."`, `"Search. Apply. Track. Follow up."`, the interlocking dual-arrow mark) appears anywhere in `apps/web` (`grep` across `apps/web` for this exact copy: zero matches). Current live hero copy is entirely different — see §4. |
| `cutout-rico-mark.png` (6.84 MB), `cutout-job-card.png` (5.40 MB), `cutout-cv-fragment.png` (5.16 MB), `cutout-status-labels.png` (6.01 MB) | png, isolated element crops from the same campaign | `cutout-status-labels.png` is **byte-identical** (verified SHA-256 match) to `600ad9a1-30fc-4802-9149-cfd085aa9cb5.html`, which is a **mislabeled PNG**, not HTML (confirmed via `file`: `PNG image data, 1744x2336`) | Isolated brand-mark / component assets, presumably for export | **UNSHIPPED / one file MISLABELED** | Current logo/mark in the live app is the "sun" motif (`RicoPresence.tsx`, `--wsx5-terra`/`--wsx5-amber` radial), not this dual-arrow mark. No conflict, just a different, unused mark concept. |

### 2.3 Video / audio

See §5 for what could and couldn't be extracted.

| Path(s) | Type / size | Duplicate group | Notes |
| --- | --- | --- | --- |
| `motion-concept.mp4` (2.21 MB) | mp4 | Byte-size-identical to `hf_20260722_212643_49b72e7d-....mp4` | Short concept clip |
| `hf_20260722_212952_835f7772-....mp4` (19.7 MB), `hf_20260722_212952_e0c2c835-....mp4` (20.9 MB), `hf_20260722_212952_56b41f69-....mp4` (22.0 MB) | mp4 | No named twins — distinct additional content | Larger, unnamed — likely alternate takes/variants of a motion concept |
| 5× `hf_2026072*_*.wav` (0.9–1.5 MB each) | wav, PCM 16-bit stereo 24kHz | No named twins | Voiceover/narration takes, unlabeled |

### 2.4 Duplicate raw exports (`hf_*` files with a named twin)

Confirmed by exact byte-size match (methodology validated by one full SHA-256 cross-check in §2.2): `hf_20260722_211733_080138ec...png` (×2 copies, one suffixed ` (1)`) = `desktop-en.png`; `hf_20260722_211733_07bdbc85...png` (×2) = `mobile-en.png`; `hf_20260722_212031_4cd2064a...png` = `arabic-desktop.png`; `hf_20260722_211733_149d7445...png` = `dark-bg.png`; `hf_20260722_212046_42a494e0...png` (×2) = `cutout-rico-mark.png`; `hf_20260722_212046_7f50a560...png` = `cutout-job-card.png`; `hf_20260722_212408_cf23fc3e...png` = `cutout-cv-fragment.png`; `hf_20260722_212643_49b72e7d...mp4` = `motion-concept.mp4`. These are raw platform-export copies of files that were also saved under a clean curated name — no distinct content. Remaining unmatched: `hf_20260722_212031_10322053...png`, `hf_20260722_212422_34766d2d...png`, `hf_20260722_212422_4d9f6097...png`, `hf_20260722_212637_0a4ae8f4...png`, `hf_20260722_233704_0aaadbc5...png` (later timestamp, 03:37 vs ~01:2x for the rest) — five extra images with no curated twin; not individually reviewed beyond size/existence (low marginal value — same campaign, same visual language as §2.2, confirmed by spot-checking two of the named twins).

---

## 3. Pricing reference vs. live billing — grounded comparison

**Live production billing `[REPO]` (verified in code, not assumed):**

- Provider: **Paddle**. `src/services/paddle_webhook_service.py`, `src/repositories/paddle_repo.py`, `apps/web/lib/paddle` (`openPaddleCheckout`, `getPaddlePriceId`), tests in `tests/test_checkout_attribution_atomic.py` and `apps/web/__tests__/paddle-event-callback.test.ts`.
- Plan structure: **exactly one paid plan** — `src/repositories/paddle_repo.py:66-69`: `id: "rico_monthly"`, `name: "Rico Monthly"`, `price_monthly: 21.50`, comment "single Rico Monthly plan (USD 21.50/month, internal tier 'pro')", capped at `monthly_ai_message_limit: 300`. Plus a Free tier (`FreePlanRow` in `SubscriptionAtelier.tsx`).
- Currency: **USD**, and explicitly, deliberately not AED — `SubscriptionAtelier.tsx:792`: footer copy `t("pricesInUSD")`, with a code comment stating "the single plan bills in USD (**Paddle does not bill AED**)".
- No yearly/annual plan exists live (no `yearly`/`annual` string anywhere in `SubscriptionAtelier.tsx`).
- Route: `/subscription` (confirmed via `LandingPageV2.tsx`'s nav: `{ label: "Rates", href: "/subscription" }`), not `/pricing`.

**Reference pack content `[LOCAL-FS]`** (`atelier-reference-pack/pr2-landing-pricing/src/routes/pricing.tsx`, from the Lovable/TanStack prototype, read from the untracked zip in `incoming/`):

- Provider: **Stripe** — the file's own developer note says verbatim: *"Create three price IDs in **Stripe**: Free, Pro Monthly (AED 79), Pro Yearly (AED 690)."* Paddle is never mentioned in this file.
- Plan structure: **three tiers** — Free (`AED 0`, "forever"), Pro Monthly (`AED 79`/month), Pro Yearly (`AED 690`/year, struck-through `AED 948`, "locked price for 12 months", "saves ~27%").
- Currency: **AED**, VAT-inclusive, explicitly the opposite framing of live ("Prices in AED, VAT included").
- Tier labels: "Reader" (free) / "Pro" — live uses "Free" / "Rico Monthly" naming instead.
- Route: `/pricing` — does not exist in the live app (confirmed: no `apps/web/app/pricing` directory).

**Conclusion — do not port as-is.** This is a genuine, confirmed conflict on three axes (billing provider, currency, tier count), not a stale-but-compatible reference. One notable nuance: AED 79 ÷ ~3.6725 (AED:USD peg) ≈ **USD 21.52** — almost exactly the live `$21.50` price point. The *price itself* likely survived from this reference into the live single-plan design; the *packaging* around it (three tiers, annual discount, Stripe, AED) did not, and re-introducing any of that would require a real product/billing decision (new Paddle price IDs, a currency-display decision Paddle itself doesn't support, and reconciling with the "single plan" simplicity that's live today) — explicitly the kind of decision `DEC-20260718-001-audit.md` says needs "explicit owner approval of... the entitlement matrix," not silent adoption.

---

## 4. Landing page — section-by-section gap map (no homepage edits made)

`[REPO]` for the "Live" column, `[LOCAL-FS]` for the "Incoming concept"
column throughout this section's table.

Live homepage: `apps/web/app/page.tsx` → for authenticated users redirects to `/command`; **for every guest, immediately hands off to a cinematic "opening film" chooser** (`goToOpeningFilm()`, rotating non-repeating options 2/3/3b, persisted in `localStorage`) per an owner directive dated 2026-07-16 (comment block at `page.tsx:6-11`). The prerendered `LandingPageV2` only appears as SEO-visible markup and on the `?after-film=1` return path — it is not most guests' first visual impression today.

| Section | Live (`LandingPageV2.tsx`) | Incoming concept (`landing-hero.png`/`desktop-en.png`) | Gap |
| --- | --- | --- | --- |
| Framing / voice | "Prospectus" / editorial-magazine voice: `"— Volume I · Issue 03"`, "Colophon" nav item, footer "meta" fields | Poster / motion-brand voice: bold stacked Fraunces headline, torn-paper desk collage | Different **voice**, not a copy edit — a full brand-direction fork |
| Hero headline | `"A career, in conversation."` (`LandingPageV2.tsx:66`) | `"YOUR CAREER, IN MOTION."` | No overlap in copy; thematically adjacent (both center "career" + a defining verb) |
| Hero subhead | "Rico is a small, patient intelligence for people looking for real work in the UAE..." | `"Search. Apply. Track. Follow up. Rico keeps the whole journey moving."` | Concept version is a literal product-loop tagline; live version is a tone/personality statement |
| Hero visual | None described in the excerpt read (interview-transcript-style hero, not a photo/illustration composite) | Full torn-paper collage: CV fragment, job-offer slip, UAE map (Dubai pin), "APPLIED" stamp, interlocking dual-arrow mark | Concept introduces an illustrated/collage visual system not present live |
| Nav | "The idea / The system / Rates / Colophon / Support" | Not visible in the still comps (no nav chrome captured) | Can't compare — asset doesn't show nav |
| Dark mode | Exists elsewhere in the app (wsx5 dark tokens), not confirmed specifically inside `LandingPageV2` from the excerpt read | Dedicated `dark-bg.png` "Atelier at Night" variant, full parity with light | Concept ships a dedicated dark landing variant explicitly designed as its own composition, not just a token swap |
| Logo/mark | Sun motif (`RicoPresence.tsx`) | Interlocking black+terra dual-arrow "infinity loop" mark | Two different mark concepts coexist; no conflict, just unused alternative |
| Guest entry point | A full-screen film (video), not a static hero, per the 2026-07-16 owner directive | Static poster-style hero | The concept doesn't address the film-first guest flow at all — before any hero copy question, there's a bigger open question of whether a static hero fits the current film-first entry model |

**Per the Landing Page Production Freeze (`AGENTS.md`, `apps/web/CLAUDE.md`), no homepage edits were made, and none are proposed here** — this is strictly a comparison for your review.

---

## 5. Motion / video / audio — metadata extracted, limitations `[LOCAL-FS]`

No code changes were made to extract this; only read-only, already-installed tools (`file`, filesystem stat) were used. **`ffprobe`/`ffmpeg` are not installed in this environment**, and no new tooling was installed to get frame/waveform/transcript data, per the instruction not to run executables — that also ruled out installing and running a new media-inspection binary without your sign-off.

| File | Container (via `file`) | Size | Notes |
| --- | --- | --- | --- |
| `motion-concept.mp4` / `hf_..._49b72e7d....mp4` | `ISO Media, MP4 Base Media v1` | 2.21 MB | Byte-identical pair |
| `hf_..._835f7772....mp4` | `ISO Media, MP4 Base Media v1` | 19.7 MB | No duration/codec/resolution extractable without `ffprobe` |
| `hf_..._e0c2c835....mp4` | `ISO Media, MP4 Base Media v1` | 20.9 MB | Same limitation |
| `hf_..._56b41f69....mp4` | `ISO Media, MP4 Base Media v1` | 22.0 MB | Same limitation |
| `hf_20260722_211307_9dee2a7b....wav` | `RIFF WAVE, Microsoft PCM, 16-bit, stereo, 24000 Hz` | 881 KB | Container confirms real speech/audio-rate PCM, consistent with narration, not silence/noise |
| Other 4 `.wav` files | Not individually probed | 0.9–1.5 MB each | Same RIFF/PCM family expected by naming pattern; not verified per-file |

**No transcripts or representative frames were produced** — that would require either `ffmpeg`/`ffprobe` or a Python media library (`cv2`/`imageio`), neither of which is present in this environment (`ModuleNotFoundError` confirmed for both; `ffprobe`/`ffmpeg` not found on `PATH`). Installing either is a reasonable follow-up but is new tooling, not a "safe metadata" read — flagging for your decision rather than doing it silently.

**Interaction ideas not already in Command V5**: none could be confirmed, precisely because frame/audio content isn't extractable here. The only evidence available (container type, size, PCM sample rate) doesn't speak to interaction design. If these clips encode motion or interaction ideas beyond what's already written down in `Rico_Command_Workspace_v5.dc.html` and `HANDOFF-rico-command-workspace-v4.md` (both of which are exhaustively specific about motion: easing curves, durations, reduced-motion collapse), that would only surface from actually watching them — recommend a quick manual pass on your end, starting with the 3 unnamed larger clips since those have no named/described counterpart anywhere else in the folder.

---

## 6. Highest-value opportunities (top 3 only)

1. **Nothing to build from the pricing reference pack as-is — it's a confirmed conflict, not a gap.** The `pricing.tsx` reference assumes Stripe + AED + 3 tiers; live is Paddle + USD + 1 tier (`src/repositories/paddle_repo.py:66-69`, `SubscriptionAtelier.tsx:792`). The one real signal worth carrying forward is that the AED 79 reference price converts to almost exactly the live $21.50 price point — suggesting the *price* was deliberately preserved even though the *packaging* wasn't. If a second (e.g., annual) plan is ever wanted, this reference is a reasonable starting *shape* for the offer structure, but needs a fresh entitlement/pricing decision from you before any implementation — not a straight port.

2. **The "Your Career, in Motion" brand concept is real, complete, and currently blocked only by the Landing Page Freeze — but it doesn't address the bigger open question first.** Before any hero-copy comparison matters, there's a structural one: guests today never see a static hero at all — they're routed straight into a full-screen film chooser (`page.tsx:39-42`, owner directive 2026-07-16). Whatever happens with this brand concept, it needs to be decided in the context of that film-first entry flow, not against `LandingPageV2` in isolation.

3. **Command Workspace v5's PR5 (motion/final-QA) is more done than `COMMAND_V5_IMPLEMENTATION_MAP.md` currently reflects.** This session shipped exactly what that PR was scoped for — hover-lift physics + Upload entrance motion (PRs `#1356`/`#1357`) — but the map document (`AI_WORKSPACE/COMMAND_V5_IMPLEMENTATION_MAP.md:28`) still lists PR5 as "not scheduled." That's a paperwork gap, not a design gap: worth a one-line update to the map so the next person doesn't re-discover the same "gap" that's actually closed.
