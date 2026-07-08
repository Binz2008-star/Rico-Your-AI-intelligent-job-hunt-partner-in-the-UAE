# Vercel Production Build Failure — Root Cause Report

**Date:** 2026-06-28  
**Reporter:** Claude (session `claude/workflow-progress-check-ar55wj`)  
**PR under investigation:** #775  
**Status:** Fixed — Vercel preview confirmed **Ready** after commit `9c04104`

---

## 1. Full build error

```
app/manifest.ts(57,17): error TS2353: Object literal may only specify known properties,
and 'label' does not exist in type
'{ src: string; type?: string | undefined; sizes?: string | undefined; }'.
```

Vercel exits non-zero at the "Linting and checking validity of types" phase of `next build`. No JavaScript is emitted; the deployment is marked failed.

---

## 2. Stack trace

This is a compile-time TypeScript type error — no runtime stack exists. The full `tsc --noEmit` output at the point of failure:

```
app/manifest.ts(57,17): error TS2353: Object literal may only specify known properties,
and 'label' does not exist in type
'{ src: string; type?: string | undefined; sizes?: string | undefined; }'.
```

---

## 3. Filename

```
apps/web/app/manifest.ts
```

---

## 4. Line number

**Line 57, column 17**

```ts
// line 54
{
    src: "/screenshots/mobile.png",
    sizes: "390x844",
    type: "image/png",
    label: "Rico Hunt Mobile — Track applications on the go",  // ← line 57, col 17
},
```

---

## 5. Root cause

The `screenshots` array in `apps/web/app/manifest.ts` contains two entries.

**Desktop entry (lines 46–52)** — has a `// @ts-expect-error` comment on line 49, placed above the non-standard `form_factor` field. TypeScript's excess-property suppression applies to the *entire object literal* when `@ts-expect-error` is present, so the `label` field on line 51 inside the same object is silently accepted.

**Mobile entry (lines 54–58)** — has no `form_factor`. Its only non-standard field is `label`. With no suppression in place, TypeScript's excess-property check fires: `label` is not present in the Next.js `MetadataRoute.Manifest` screenshot type (`{ src: string; type?: string; sizes?: string }`).

The inconsistency was an oversight in the original commit: the desktop object's `@ts-expect-error` on `form_factor` happened to cover `label` too, masking the gap. The mobile object had no such cover.

---

## 6. Introduced on `main` or by PR #775?

**Introduced on `main`** — commit `f63181a` ("fix(seo): full structured data pass — Organization+, FAQ, Breadcrumb, SoftwareApplication+, sitemap, manifest, OG image v2"), merged **before** PR #775 was opened.

Commit `f63181a` is present on `origin/main`. PR #775 did not touch `manifest.ts` in any of its P2-A commits (`a24f765`, `0a872fd`).

The production deployment failure reported via email at 10:26 AM was therefore a **pre-existing break on `main`**, unrelated to PR #775.

---

## 7. Minimal fix

Add one `// @ts-expect-error` comment on the line immediately before the `label` field in the mobile screenshot entry:

```diff
 {
     src: "/screenshots/mobile.png",
     sizes: "390x844",
     type: "image/png",
+    // @ts-expect-error: label is a valid PWA manifest field not yet typed by Next.js
     label: "Rico Hunt Mobile — Track applications on the go",
 },
```

No logic change. No structural change. One comment line suppressing a spurious type complaint about a valid [Web App Manifest `screenshots` member](https://developer.mozilla.org/en-US/docs/Web/Manifest/screenshots).

---

## 8. Verification

| Step | Result |
|---|---|
| `tsc --noEmit --skipLibCheck` on unfixed `origin/main` manifest | `TS2353` error at line 57 confirmed |
| `tsc --noEmit --skipLibCheck` on fixed branch | No errors |
| `npm run build` on fixed branch | Succeeded — all 39 pages generated |
| Vercel preview build after fix push | **Ready** (deployment `HPS7BunAGcQU2bxfM5zxNvp7J9kZ`) |

---

## 9. Action required

The fix is committed on `claude/workflow-progress-check-ar55wj` (commit `9c04104`) as part of PR #775. Merging PR #775 to `main` will resolve the production deployment failure.
