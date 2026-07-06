# Rico — Landing polish: developer handoff (forward this to the dev)

**From:** design review · **For:** whoever maintains `apps/web`
**Type:** frontend-only, low-risk. No backend, no auth, no routing, no new dependencies.

## Context (1 paragraph)
The approved luxury landing direction (flowing cyan/magenta ribbon background + premium
hover feature cards) is **already implemented** in `apps/web/components/LandingPageV2.tsx`.
This handoff is a small **hardening** pass on the existing ribbon animation only — the
visuals do not change.

## The one change
Replace the `useRibbonCanvas` hook in `apps/web/components/LandingPageV2.tsx` with the
hardened version below. It:
- switches the animation driver from `setInterval` to `requestAnimationFrame`
  (throttled to ~33 ms so the motion speed is identical),
- pauses on `visibilitychange` (stops when the tab/page is hidden),
- renders a single static frame under `prefers-reduced-motion: reduce`
  (previously the canvas went blank),
- cleans up the rAF + listener on unmount.

Same 42/22 ribbon density, same colors, same look — no visual change.

```tsx
/* ─── Canvas ribbon animation ─────────────────────────────────────────────── */
function useRibbonCanvas(canvasRef: React.RefObject<HTMLCanvasElement | null>) {
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        interface RibbonLine {
            segs: { x: number; y: number }[];
            isMag: boolean;
            spd: number;
            phase: number;
            alpha: number;
        }

        let W = 0, H = 0;
        let lines: RibbonLine[] = [];
        let raf = 0;
        let last = 0;
        let running = false;
        let t = 0;

        function resize() {
            W = canvas!.width = canvas!.offsetWidth;
            H = canvas!.height = canvas!.offsetHeight;
            buildLines();
        }

        function buildLines() {
            const n = W < 700 ? 22 : 42;                 // low-density mobile mode
            const SX = W * 0.96;
            const SY = H * 0.04;
            lines = [];
            for (let i = 0; i < n; i++) {
                const spread = (i - n / 2) * 0.055;
                const segs: { x: number; y: number }[] = [];
                const L = 300;
                let cx = SX, cy = SY;
                let ang = Math.PI + spread * 0.0052 + (Math.random() - 0.5) * 0.04;
                for (let s = 0; s < L; s++) {
                    segs.push({ x: cx, y: cy });
                    ang += (Math.random() - 0.5) * 0.018;
                    cx += Math.cos(ang) * 8;
                    cy += Math.sin(ang) * 8;
                }
                lines.push({
                    segs,
                    isMag: Math.random() < 0.28,
                    spd: 0.4 + Math.random() * 0.6,
                    phase: Math.random() * 370,
                    alpha: 0.12 + Math.random() * 0.18,
                });
            }
        }

        function draw() {
            ctx!.clearRect(0, 0, W, H);
            for (const L of lines) {
                const len = L.segs.length;
                const head = ((t * L.spd + L.phase) % (len + 70));
                const tailN = 28;
                for (let s = 1; s < len; s++) {
                    const a = L.segs[s - 1], b = L.segs[s];
                    const dist = Math.abs(s - head);
                    let alpha = L.alpha * 0.35;
                    if (dist < tailN) {
                        const bright = 1 - dist / tailN;
                        alpha = L.alpha * (0.35 + bright * 1.2);
                    }
                    ctx!.beginPath();
                    ctx!.moveTo(a.x, a.y);
                    ctx!.lineTo(b.x, b.y);
                    ctx!.lineWidth = dist < tailN ? 1.5 + (1 - dist / tailN) * 1.5 : 1;
                    if (L.isMag) {
                        ctx!.strokeStyle = dist < 4 ? `rgba(255,150,190,${alpha})` : `rgba(255,72,149,${alpha})`;
                    } else {
                        ctx!.strokeStyle = dist < 4 ? `rgba(150,240,255,${alpha})` : `rgba(0,218,243,${alpha})`;
                    }
                    ctx!.stroke();
                }
            }
        }

        // requestAnimationFrame, throttled to ~30fps so motion speed is IDENTICAL
        // to the previous setInterval(draw, 33) implementation.
        const FRAME_MS = 33;
        function loop(now: number) {
            if (!running) return;
            raf = requestAnimationFrame(loop);
            if (now - last < FRAME_MS) return;
            last = now;
            t += 1;
            draw();
        }
        function start() {
            if (running || reduced || document.hidden) return;
            running = true;
            last = performance.now();
            raf = requestAnimationFrame(loop);
        }
        function stop() {
            running = false;
            cancelAnimationFrame(raf);
        }

        resize();
        const ro = new ResizeObserver(resize);
        ro.observe(canvas);

        // Reduced motion → render ONE static frame, never animate.
        if (reduced) {
            t = 120;
            draw();
            return () => ro.disconnect();
        }

        // Pause when the tab/page is hidden; resume when visible.
        const onVisibility = () => (document.hidden ? stop() : start());
        document.addEventListener("visibilitychange", onVisibility);

        start();

        return () => {
            stop();
            document.removeEventListener("visibilitychange", onVisibility);
            ro.disconnect();
        };
    }, [canvasRef]);
}
```

## PR
- **Title:** `landing: harden hero ribbon canvas (rAF + visibility pause + reduced-motion static)`
- **Files changed:** `apps/web/components/LandingPageV2.tsx` (one hook). Nothing else.
- **Do NOT touch:** command/chat, auth (`login`/`signup`), backend `src/**`, jobs/CV/
  applications/billing, routing, framework versions, pricing, Telegram workflow,
  `globals.css`, `tailwind.config.ts`.

## Acceptance checklist
- [ ] `cd apps/web && npm run build` passes
- [ ] `npm run test` (vitest) + `npm run lint` pass
- [ ] `/` loads and ribbons animate; `/login`, `/signup`, `/command` load unchanged
- [ ] Switch browser tab away/back → animation pauses/resumes
- [ ] Emulate `prefers-reduced-motion: reduce` → static frame, no motion, no console errors
- [ ] No console errors from the landing

## Separate copy follow-up (optional, not this PR)
On the landing, soften three unverified claims for a polished, honest first impression:
1. **Success Stories** use fabricated candidates + match scores → mark as illustrative or
   replace with real, consented testimonials.
2. Hero demo card **"Live listing"** sits on static demo data → reword so it doesn't imply real-time.
3. **Employer logo marquee** implies sourcing/endorsement → keep only employers whose
   listings Rico genuinely surfaces.
