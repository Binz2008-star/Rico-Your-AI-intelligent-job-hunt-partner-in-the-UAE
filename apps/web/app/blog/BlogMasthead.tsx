"use client";

import Link from "next/link";
import { useLanguage } from "@/contexts/LanguageContext";
import { ATELIER as C, ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { Mono } from "@/components/atelier-kit/primitives";

const SERIF = ATELIER_FONT.serif;
const MONO = ATELIER_FONT.mono;

/* Scoped interaction/typography CSS for the blog routes — mirrors the
   `.lpv2-root` rules on the production landing (hover = color shift, visible
   focus ring, Arabic letter-spacing/italic guards) under a `.rblog-root`
   scope so the two surfaces stay independent. */
export const BLOG_SCOPED_CSS = `
.rblog-root { --rblog-ink:#1F1B15; --rblog-sun:#C6492E; }
.rblog-root .rblog-nav, .rblog-root .rblog-openrico { transition: color .2s ease, border-color .2s ease; }
.rblog-root .rblog-nav:hover span { color: var(--rblog-ink); }
.rblog-root .rblog-openrico:hover { border-bottom-color: var(--rblog-sun); }
.rblog-root .rblog-openrico:hover span { color: var(--rblog-sun); }
.rblog-root .rblog-card .rblog-title { transition: color .2s ease; }
.rblog-root .rblog-card:hover .rblog-title { color: var(--rblog-sun); }
.rblog-root .rblog-cta { transition: background-color .2s ease; }
.rblog-root .rblog-cta:hover { background-color: var(--rblog-sun); }
.rblog-root a:focus-visible, .rblog-root button:focus-visible { outline: 2px solid var(--rblog-sun); outline-offset: 3px; border-radius: 2px; }
.rblog-root .rblog-pulse { animation: rblog-pulse 2.4s cubic-bezier(0.4,0,0.6,1) infinite; }
@keyframes rblog-pulse { 0%,100% { opacity:1 } 50% { opacity:.35 } }
.rblog-root.rblog-ar, .rblog-root.rblog-ar * { letter-spacing: 0 !important; }
.rblog-root.rblog-ar .uppercase { font-family: var(--font-body), var(--font-sans-arabic, "Noto Sans Arabic"), ui-sans-serif, system-ui, sans-serif !important; }
.rblog-root.rblog-ar .italic { font-style: normal; }
@media (prefers-reduced-motion: reduce) { .rblog-root .rblog-pulse { animation: none !important; } }
`;

/** Editorial masthead for the blog routes — condensed from the production
 *  landing's Masthead so /blog reads as the same publication. */
export function BlogMasthead() {
  const { language, setLanguage } = useLanguage();
  const isAr = language === "ar";
  const arrow = isAr ? "←" : "→";

  return (
    <header style={{ borderBottom: `1px solid ${C.hair}` }}>
      <div className="max-w-6xl mx-auto px-5 sm:px-8">
        <div className="flex items-center justify-between py-4 gap-4">
          <div className="flex items-baseline gap-3 min-w-0">
            <Link href="/" className="text-[1.35rem] leading-none tracking-tight" style={{ fontFamily: SERIF, color: C.ink }}>
              Rico Hunt
            </Link>
            <Mono className="hidden sm:inline" style={{ color: C.ink55, letterSpacing: "0.18em" }}>
              {isAr ? "— الأدلّة المهنيّة" : "— Career Guides"}
            </Mono>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/blog" className="rblog-nav hidden sm:inline">
              <Mono style={{ color: C.ink70, letterSpacing: "0.16em" }}>{isAr ? "كل الأدلّة" : "All guides"}</Mono>
            </Link>
            <span className="inline-flex items-center rounded-[3px] overflow-hidden" style={{ border: `1px solid ${C.hair}` }}>
              <button
                type="button"
                onClick={() => setLanguage("en")}
                aria-pressed={!isAr}
                style={{ fontFamily: MONO, fontSize: 10, padding: "3px 7px", background: !isAr ? C.ink : "transparent", color: !isAr ? C.panel : C.ink40, cursor: "pointer" }}
              >
                EN
              </button>
              <button
                type="button"
                onClick={() => setLanguage("ar")}
                aria-pressed={isAr}
                style={{ fontFamily: MONO, fontSize: 10, padding: "3px 7px", background: isAr ? C.ink : "transparent", color: isAr ? C.panel : C.ink40, cursor: "pointer" }}
              >
                عر
              </button>
            </span>
            <Link href="/command" className="rblog-openrico whitespace-nowrap" style={{ borderBottom: `1px solid ${C.ink}` }}>
              <span style={{ fontFamily: isAr ? ATELIER_FONT.body : MONO, fontSize: 12, color: C.ink }}>
                {isAr ? `افتح ريكو ${arrow}` : `Open Rico ${arrow}`}
              </span>
            </Link>
          </div>
        </div>
        <div className="flex items-center gap-4 pb-3">
          <Mono style={{ color: C.ink55, letterSpacing: "0.16em" }}>
            {isAr ? "دبي · أبوظبي · الشارقة · ٢٠٢٦" : "Dubai · Abu Dhabi · Sharjah · 2026"}
          </Mono>
          <span className="h-px flex-1" style={{ background: C.hair }} aria-hidden="true" />
          <Mono className="hidden sm:inline" style={{ color: C.ink55, letterSpacing: "0.16em" }}>
            {isAr ? "العربية · English" : "العربية · English"}
          </Mono>
        </div>
      </div>
    </header>
  );
}
