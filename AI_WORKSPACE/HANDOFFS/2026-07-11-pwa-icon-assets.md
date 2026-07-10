# Handoff — Rico PWA icon assets

Status: ready for review
Date: 2026-07-11
Branch: `assets/rico-pwa-icons`

## Purpose

Replace the temporary/generated PWA icons with the Rico compass artwork supplied by the owner, and leave the asset paths documented so a later Claude session can continue safely.

## Files delivered

- `apps/web/public/icons/icon-192.png` — standard 192×192 PWA icon
- `apps/web/public/icons/icon-512.png` — standard 512×512 PWA icon
- `apps/web/public/icons/icon-maskable-192.png` — dedicated 192×192 maskable icon
- `apps/web/public/icons/icon-maskable-512.png` — dedicated 512×512 maskable icon
- `apps/web/public/apple-touch-icon.png` — 180×180 Apple touch icon
- `apps/web/app/manifest.ts` — maskable entries now reference the dedicated maskable files

## Scope and constraints

- Assets and manifest references only.
- No application logic, routing, authentication, database, or backend behavior changed.
- The supplied compass artwork remains the visual source of truth.
- `apps/web/app/icon.svg` and the current favicon metadata are not changed in this focused PWA asset update; Claude may review those separately if the owner wants all browser/favicon surfaces aligned later.

## Verification expected before merge

1. Confirm every PNG opens as a valid binary image.
2. Confirm exact dimensions: 192×192, 512×512, and 180×180.
3. Build the Next.js app and inspect the generated web manifest.
4. Run a PWA/installability check and confirm Android uses the maskable variants without unsafe cropping.
5. Check the Apple home-screen icon on an iOS device or simulator when available.
