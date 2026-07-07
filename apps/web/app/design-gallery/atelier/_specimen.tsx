"use client";

/**
 * ATELIER V2 — DESIGN SYSTEM SPECIMEN  ·  /design-gallery/atelier
 *
 * Internal, noindex preview of the approved Atelier V2 design direction
 * (Lovable design handoff). This is PR A1 of the V2 cutover: tokens + fonts +
 * specimen ONLY. It is fully isolated:
 *
 *  - All styling is scoped under `.atelier` (see ./atelier.css) — nothing here
 *    can affect any production surface.
 *  - Theme (light/dark) and language/direction (EN/AR) are LOCAL component
 *    state. They do NOT read or write the site ThemeProvider / LanguageProvider,
 *    localStorage, or the global <html> class. Toggling here changes only this
 *    specimen, never production.
 *  - No backend, auth, billing, or data access. All copy is static sample text.
 *
 * This component was authored for Next.js + React; it is NOT copied from the
 * TanStack/Lovable prototype.
 */

import Link from "next/link";
import { useState } from "react";
import "./atelier.css";

type Theme = "light" | "dark";
type Lang = "en" | "ar";

interface Token {
    name: string;
    light: string;
    dark: string;
    role: string;
}

// Approved Atelier palette (DESIGN-HANDOFF.md §2).
const TOKENS: Token[] = [
    { name: "--paper", light: "#f2ece0", dark: "#16130e", role: "Background" },
    { name: "--paper-2", light: "#e8dfcd", dark: "#1f1a12", role: "Raised surface" },
    { name: "--ink", light: "#14110d", dark: "#f2ece0", role: "Primary text" },
    { name: "--ink-soft", light: "#3a342c", dark: "#d7cebc", role: "Secondary text" },
    { name: "--ink-mute", light: "#6b6355", dark: "#9a907d", role: "Muted text" },
    { name: "--rule", light: "#d3c9b4", dark: "#35302a", role: "Hairline borders" },
    { name: "--sun", light: "#cf3d17", dark: "#ee6a3a", role: "Accent / CTA / ring" },
    { name: "--sun-soft", light: "#ea8a4e", dark: "#f0a170", role: "Accent tint" },
    { name: "--destructive", light: "#b23a1a", dark: "#d6552e", role: "Errors" },
];

// Bilingual sample copy. Follows copy-notes.md: MSA (not Gulf dialect), no
// exclamation marks/emoji, brand name "Rico" stays Latin, Latin digits inside
// Arabic, AED as an LTR island.
const COPY: Record<Lang, {
    eyebrow: string;
    headline: string;
    body: string;
    cardTitle: string;
    cardBody: string;
    cta: string;
    secondary: string;
    fieldLabel: string;
    fieldPlaceholder: string;
    notesLabel: string;
    notesPlaceholder: string;
    salaryLabel: string;
    badgeMatch: string;
    badgeNew: string;
    badgeClosed: string;
    rtlNote: string;
}> = {
    en: {
        eyebrow: "AI Career Operator · United Arab Emirates",
        headline: "A calmer way to run your job search.",
        body:
            "Rico works quietly in the background — reading your CV, matching real UAE roles, and keeping every application on track. In English or Arabic, on your terms.",
        cardTitle: "Match analysis",
        cardBody:
            "Rico scores each role against your profile and explains the reasoning, so you decide with context — not guesswork.",
        cta: "Start with Rico",
        secondary: "Upload CV",
        fieldLabel: "Target role",
        fieldPlaceholder: "e.g. HSE Manager",
        notesLabel: "Notes for Rico",
        notesPlaceholder: "Anything Rico should keep in mind…",
        salaryLabel: "Expected salary",
        badgeMatch: "Strong match",
        badgeNew: "New",
        badgeClosed: "Closed",
        rtlNote:
            "Layout uses logical properties, so it mirrors cleanly in Arabic. The arrow flips; the salary stays left-to-right.",
    },
    ar: {
        eyebrow: "مشغّل مهني بالذكاء الاصطناعي · الإمارات العربية المتحدة",
        headline: "طريقة أهدأ لإدارة بحثك عن عمل.",
        body:
            "يعمل Rico بهدوء في الخلفية — يقرأ سيرتك الذاتية، ويطابق وظائف حقيقية في الإمارات، ويتابع كل طلب توظيف. بالعربية أو الإنجليزية، وفق شروطك.",
        cardTitle: "تحليل التطابق",
        cardBody:
            "يقيّم Rico كل وظيفة بناءً على ملفك المهني ويشرح الأسباب، لتقرر بوضوح لا بالتخمين.",
        cta: "ابدأ مع Rico",
        secondary: "رفع السيرة الذاتية",
        fieldLabel: "الوظيفة المستهدفة",
        fieldPlaceholder: "مثال: مدير الصحة والسلامة",
        notesLabel: "ملاحظات إلى Rico",
        notesPlaceholder: "أي شيء ينبغي أن يأخذه Rico في الحسبان…",
        salaryLabel: "الراتب المتوقع",
        badgeMatch: "تطابق قوي",
        badgeNew: "جديد",
        badgeClosed: "مغلق",
        rtlNote:
            "يعتمد التخطيط على الخصائص المنطقية، فينعكس بنظافة في العربية. ينقلب السهم، ويبقى الراتب من اليسار إلى اليمين.",
    },
};

export default function AtelierSpecimen() {
    const [theme, setTheme] = useState<Theme>("light");
    const [lang, setLang] = useState<Lang>("en");
    const dir = lang === "ar" ? "rtl" : "ltr";
    const t = COPY[lang];

    return (
        <div className="atelier" data-atl-theme={theme} dir={dir} lang={lang}>
            {/* ── Control bar ─────────────────────────────────────────────────── */}
            <div className="atl-bar" dir="ltr">
                <span className="atl-badge-internal">
                    Internal preview · not production navigation
                </span>
                <span className="atl-meta">Atelier V2 · design system</span>
                <div style={{ flex: 1 }} />
                <button
                    type="button"
                    className="atl-toggle"
                    onClick={() => setTheme((v) => (v === "light" ? "dark" : "light"))}
                    aria-pressed={theme === "dark"}
                >
                    {theme === "light" ? "◐ Light" : "◑ Dark"}
                </button>
                <button
                    type="button"
                    className="atl-toggle"
                    onClick={() => setLang((v) => (v === "en" ? "ar" : "en"))}
                    aria-pressed={lang === "ar"}
                >
                    {lang === "en" ? "EN → العربية" : "العربية → EN"}
                </button>
                <Link href="/design-gallery" className="atl-link-back" dir="ltr">
                    ← gallery
                </Link>
            </div>

            <div className="atl-wrap">
                {/* ── Hero / typography-in-context ────────────────────────────── */}
                <div className="atl-eyebrow">
                    <span className="atl-dot" />
                    {t.eyebrow}
                </div>
                <h1 className="atl-display atl-d1" style={{ marginTop: 18 }}>
                    {t.headline}
                </h1>
                <p className="atl-body" style={{ marginTop: 18 }}>
                    {t.body}
                </p>
                <div className="atl-row" style={{ marginTop: 24 }}>
                    <button type="button" className="atl-btn atl-btn-primary">
                        {t.cta} <span className="atl-arrow">→</span>
                    </button>
                    <button type="button" className="atl-btn atl-btn-outline">
                        {t.secondary}
                    </button>
                </div>

                {/* ── Color tokens ────────────────────────────────────────────── */}
                <section className="atl-section">
                    <div className="atl-section-label">Color tokens · {theme}</div>
                    <div className="atl-swatches">
                        {TOKENS.map((tok) => (
                            <div className="atl-swatch" key={tok.name}>
                                <div
                                    className="atl-swatch-chip"
                                    style={{ background: theme === "light" ? tok.light : tok.dark }}
                                />
                                <div className="atl-swatch-meta">
                                    <div className="atl-swatch-name">{tok.name}</div>
                                    <div className="atl-swatch-hex">
                                        {theme === "light" ? tok.light : tok.dark} · {tok.role}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>

                {/* ── Typography ──────────────────────────────────────────────── */}
                <section className="atl-section">
                    <div className="atl-section-label">Typography</div>
                    <p className="atl-meta" style={{ marginBottom: 6 }}>
                        Display — {dir === "rtl" ? "Amiri" : "Fraunces"}
                    </p>
                    <p className="atl-display atl-d2">{t.headline}</p>
                    <p className="atl-meta" style={{ margin: "22px 0 6px" }}>
                        Body — {dir === "rtl" ? "IBM Plex Sans Arabic" : "Inter"}
                    </p>
                    <p className="atl-body">{t.body}</p>
                    <p className="atl-meta" style={{ margin: "22px 0 6px" }}>
                        Meta / mono — IBM Plex Mono
                    </p>
                    <p className="atl-meta">
                        AI CAREER OPERATOR · UNITED ARAB EMIRATES ·{" "}
                        <span className="atl-ltr-island">AED 12,000</span>
                    </p>
                </section>

                {/* ── Buttons ─────────────────────────────────────────────────── */}
                <section className="atl-section">
                    <div className="atl-section-label">Buttons</div>
                    <div className="atl-row">
                        <button type="button" className="atl-btn atl-btn-primary">Primary</button>
                        <button type="button" className="atl-btn atl-btn-outline">Outline</button>
                        <button type="button" className="atl-btn atl-btn-ghost">Ghost</button>
                        <button type="button" className="atl-btn atl-btn-destructive">Destructive</button>
                        <button type="button" className="atl-btn atl-btn-primary" disabled>Disabled</button>
                    </div>
                </section>

                {/* ── Cards ───────────────────────────────────────────────────── */}
                <section className="atl-section">
                    <div className="atl-section-label">Cards</div>
                    <div className="atl-cards">
                        <article className="atl-card">
                            <span className="atl-badge atl-badge-accent">{t.badgeMatch}</span>
                            <h3 className="atl-card-title">{t.cardTitle}</h3>
                            <p className="atl-card-body">{t.cardBody}</p>
                            <div className="atl-card-foot">
                                <span className="atl-meta">
                                    <span className="atl-ltr-island">AED 12,000</span> / mo
                                </span>
                                <button type="button" className="atl-btn atl-btn-outline">
                                    {t.secondary}
                                </button>
                            </div>
                        </article>
                        <article className="atl-card">
                            <span className="atl-badge atl-badge-solid">{t.badgeNew}</span>
                            <h3 className="atl-card-title">Rico</h3>
                            <p className="atl-card-body">{t.body}</p>
                            <div className="atl-card-foot">
                                <span className="atl-meta">SAMPLE · demo data</span>
                                <span className="atl-arrow atl-meta">→</span>
                            </div>
                        </article>
                    </div>
                </section>

                {/* ── Form inputs ─────────────────────────────────────────────── */}
                <section className="atl-section">
                    <div className="atl-section-label">Form inputs</div>
                    <div className="atl-field">
                        <label className="atl-label" htmlFor="atl-role">{t.fieldLabel}</label>
                        <input
                            id="atl-role"
                            className="atl-input"
                            placeholder={t.fieldPlaceholder}
                            defaultValue=""
                        />
                    </div>
                    <div className="atl-field">
                        <label className="atl-label" htmlFor="atl-salary">{t.salaryLabel}</label>
                        <select id="atl-salary" className="atl-select" defaultValue="">
                            <option value="" disabled>AED 8,000 – 30,000</option>
                            <option value="a">AED 8,000 – 12,000</option>
                            <option value="b">AED 12,000 – 20,000</option>
                            <option value="c">AED 20,000 – 30,000</option>
                        </select>
                    </div>
                    <div className="atl-field">
                        <label className="atl-label" htmlFor="atl-notes">{t.notesLabel}</label>
                        <textarea
                            id="atl-notes"
                            className="atl-textarea"
                            placeholder={t.notesPlaceholder}
                        />
                    </div>
                </section>

                {/* ── Badges ──────────────────────────────────────────────────── */}
                <section className="atl-section">
                    <div className="atl-section-label">Badges</div>
                    <div className="atl-row">
                        <span className="atl-badge">{t.badgeClosed}</span>
                        <span className="atl-badge atl-badge-accent">{t.badgeMatch}</span>
                        <span className="atl-badge atl-badge-solid">{t.badgeNew}</span>
                        <span className="atl-badge atl-badge-danger">{t.badgeClosed}</span>
                    </div>
                </section>

                {/* ── RTL / bidi demonstration ────────────────────────────────── */}
                <section className="atl-section">
                    <div className="atl-section-label">RTL &amp; bidi · dir={dir}</div>
                    <div className="atl-split">
                        <div className="atl-card">
                            <div className="atl-eyebrow" style={{ marginBottom: 10 }}>
                                <span className="atl-dot" />
                                {t.fieldLabel}
                            </div>
                            <p className="atl-card-body">{t.rtlNote}</p>
                            <div className="atl-card-foot">
                                <button type="button" className="atl-btn atl-btn-ghost">
                                    <span className="atl-arrow">→</span> {t.cta}
                                </button>
                                <span className="atl-meta">
                                    <span className="atl-ltr-island">AED 12,000</span>
                                </span>
                            </div>
                        </div>
                    </div>
                    <p className="atl-meta" style={{ marginTop: 14 }}>
                        Toggle EN → العربية in the top bar to flip direction, fonts, and the arrow glyph.
                    </p>
                </section>
            </div>
        </div>
    );
}
