"use client";

/**
 * DESIGN GALLERY PROTOTYPE — Rico Ascent
 *
 * Standalone component for /design-gallery only. NOT the homepage, NOT /command,
 * NOT linked from production navigation. All step timing/content below is a
 * SAMPLE SEQUENCE — no real AI calls, no real jobs, no live provider traffic.
 *
 * Explores a bolder Rico visual/motion language built on top of the ratified
 * Nocturne palette (navy canvas, gold/indigo/teal accents) rather than
 * replacing it: an asymmetric editorial hero with a real generated visual,
 * and an interactive "what happens when you ask Rico something" sequence
 * that is the actual flagship deliverable — motion standing in for Rico's
 * real working order (context → understanding → search → read → verify →
 * approval-gated → one of three honest outcomes), not decorative animation.
 *
 * Bilingual EN / Arabic (RTL), reduced-motion aware, zero new runtime deps
 * beyond fonts (next/font/google, build-time) — framer-motion + lucide-react
 * are both already project dependencies.
 */

import { useEffect, useRef, useState, type CSSProperties } from "react";
import Image from "next/image";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Radar,
  Fingerprint,
  Search,
  FileText,
  ShieldCheck,
  Hand,
  ArrowUpRight,
  Languages,
  CheckCircle2,
  HelpCircle,
  RefreshCcw,
} from "lucide-react";
import { ricoAscentFontVars } from "./fonts";
import { RICO_ASCENT_COPY, type Lang } from "./content";

/* ─── Nocturne palette (literal — isolated from any global theme class) ──── */
const navy = "rgb(11,13,28)";
const surface = "rgb(16,20,42)";
const gold = "rgb(240,169,74)";
const teal = "rgb(111,233,208)";
const indigo = "rgb(129,140,248)";
const ink70 = "rgba(255,255,255,0.70)";
const ink45 = "rgba(255,255,255,0.45)";
const ink25 = "rgba(255,255,255,0.25)";
const hairline = "rgba(255,255,255,0.10)";

const STEP_ICONS = [Radar, Fingerprint, Search, FileText, ShieldCheck, Hand, ArrowUpRight];

function useIsRtl(lang: Lang) {
  return lang === "ar";
}

export default function RicoAscent() {
  const [lang, setLang] = useState<Lang>("en");
  const copy = RICO_ASCENT_COPY[lang];
  const rtl = useIsRtl(lang);
  const reduce = useReducedMotion();

  const bodyFontFamily = rtl
    ? `var(--font-ra-arabic), system-ui, sans-serif`
    : `var(--font-ra-body), system-ui, sans-serif`;
  const displayFontFamily = rtl
    ? `var(--font-ra-arabic), system-ui, sans-serif`
    : `var(--font-ra-display), system-ui, sans-serif`;

  return (
    <div
      dir={copy.dir}
      className={ricoAscentFontVars}
      style={{
        background: navy,
        color: "white",
        fontFamily: bodyFontFamily,
        minHeight: "100vh",
        overflowX: "hidden",
      }}
    >
      <Hero lang={lang} setLang={setLang} rtl={rtl} reduce={!!reduce} displayFont={displayFontFamily} bodyFont={bodyFontFamily} />
      <Moment rtl={rtl} reduce={!!reduce} copy={copy.moment} displayFont={displayFontFamily} bodyFont={bodyFontFamily} />
      <Closing rtl={rtl} reduce={!!reduce} copy={copy.closing} displayFont={displayFontFamily} bodyFont={bodyFontFamily} />
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   HERO — asymmetric split, one CTA, real generated visual, no eyebrow spam
   ════════════════════════════════════════════════════════════════════════ */

function Hero({
  lang,
  setLang,
  rtl,
  reduce,
  displayFont,
  bodyFont,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  rtl: boolean;
  reduce: boolean;
  displayFont: string;
  bodyFont: string;
}) {
  const copy = RICO_ASCENT_COPY[lang].hero;
  const toggleLabel = RICO_ASCENT_COPY[lang].langToggleLabel;

  return (
    <section
      style={{ position: "relative" }}
      className="grid grid-cols-1 lg:grid-cols-[1.05fr_0.95fr] lg:min-h-[100dvh] items-center px-5 lg:px-16 pt-6"
    >
      {/* Language toggle — single control, top corner */}
      <button
        onClick={() => setLang(lang === "en" ? "ar" : "en")}
        style={{
          position: "absolute",
          top: 20,
          [rtl ? "left" : "right"]: 20,
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
          fontFamily: `var(--font-ra-mono), monospace`,
          padding: "6px 12px",
          borderRadius: 999,
          border: `1px solid ${hairline}`,
          background: "rgba(255,255,255,0.04)",
          color: ink70,
          cursor: "pointer",
          zIndex: 20,
        } as CSSProperties}
        aria-label="Switch language"
      >
        <Languages size={13} strokeWidth={1.75} />
        {toggleLabel}
      </button>

      {/* Ambient rail motif echoing the hero image's ascending waypoints — pure decoration, ok since it's a background wash, not a content element */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(60% 50% at 15% 20%, rgba(240,169,74,0.08), transparent 60%), radial-gradient(50% 40% at 85% 75%, rgba(111,233,208,0.06), transparent 60%)",
          pointerEvents: "none",
        }}
      />

      {/* Copy column */}
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        style={{ position: "relative", zIndex: 10, maxWidth: 620, padding: "96px 0 56px" }}
      >
        <h1
          style={{
            fontFamily: displayFont,
            fontWeight: 600,
            fontSize: "clamp(2.4rem, 5.4vw, 4.1rem)",
            lineHeight: 1.06,
            letterSpacing: "-0.02em",
            margin: 0,
            maxWidth: "14ch",
          }}
        >
          {copy.headline}
        </h1>
        <p
          style={{
            fontFamily: bodyFont,
            fontSize: "1.05rem",
            lineHeight: 1.6,
            color: ink70,
            marginTop: 24,
            maxWidth: "46ch",
          }}
        >
          {copy.subtext}
        </p>
        <a
          href="/command"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            marginTop: 36,
            padding: "13px 26px",
            borderRadius: 999,
            background: gold,
            color: navy,
            fontWeight: 600,
            fontSize: "0.95rem",
            textDecoration: "none",
            fontFamily: bodyFont,
            whiteSpace: "nowrap",
          }}
        >
          {copy.cta}
          <ArrowUpRight size={17} strokeWidth={2.25} style={rtl ? { transform: "scaleX(-1)" } : undefined} />
        </a>
      </motion.div>

      {/* Visual column — real generated image, full bleed, edge-fade mask (no card radius / no fake screenshot) */}
      <motion.div
        initial={reduce ? false : { opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: reduce ? 0 : 0.1 }}
        style={{
          position: "relative",
          width: "100%",
          aspectRatio: "16 / 10",
          marginTop: 8,
          marginBottom: 24,
        }}
      >
        <Image
          src="/design-gallery/rico-ascent-hero.png"
          alt=""
          fill
          priority
          sizes="(min-width: 1024px) 45vw, 100vw"
          style={{
            objectFit: "cover",
            maskImage: "linear-gradient(to bottom, transparent 0%, black 14%, black 88%, transparent 100%)",
            WebkitMaskImage: "linear-gradient(to bottom, transparent 0%, black 14%, black 88%, transparent 100%)",
          }}
        />
        {/* Edge blend into canvas on the side adjacent to the copy column */}
        <div
          aria-hidden
          style={{
            position: "absolute",
            inset: 0,
            background: rtl
              ? `linear-gradient(to left, ${navy} 0%, transparent 14%, transparent 100%)`
              : `linear-gradient(to right, ${navy} 0%, transparent 14%, transparent 100%)`,
            pointerEvents: "none",
          }}
        />
      </motion.div>
    </section>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   MOMENT — the flagship piece. An interactive 7-stop sequence that stands
   in for Rico's real working order, ending in a 3-way honest outcome branch
   (completion / uncertainty / recovery) instead of a fake "always succeeds"
   demo. Auto-advances; clicking a node jumps directly and resets the timer.
   Under reduced motion: no auto-advance, no looping ambient motion, instant
   state changes only on explicit click.
   ════════════════════════════════════════════════════════════════════════ */

const STEP_MS = 2600;

function Moment({
  rtl,
  reduce,
  copy,
  displayFont,
  bodyFont,
}: {
  rtl: boolean;
  reduce: boolean;
  copy: (typeof RICO_ASCENT_COPY)["en"]["moment"];
  displayFont: string;
  bodyFont: string;
}) {
  const steps = copy.steps;
  const [active, setActive] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isOutcome = active === steps.length - 1;

  useEffect(() => {
    if (reduce) return; // no autoplay under reduced motion
    timerRef.current = setInterval(() => {
      setActive((a) => (a + 1) % steps.length);
    }, STEP_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [reduce, steps.length]);

  function jumpTo(i: number) {
    setActive(i);
    if (timerRef.current) clearInterval(timerRef.current);
    if (!reduce) {
      timerRef.current = setInterval(() => {
        setActive((a) => (a + 1) % steps.length);
      }, STEP_MS);
    }
  }

  const ActiveIcon = STEP_ICONS[active];

  return (
    <section
      style={{
        position: "relative",
        padding: "88px 20px 100px",
        maxWidth: 980,
        margin: "0 auto",
      }}
    >
      <span
        style={{
          display: "inline-block",
          fontSize: 10.5,
          fontFamily: `var(--font-ra-mono), monospace`,
          textTransform: rtl ? "none" : "uppercase",
          letterSpacing: rtl ? "normal" : "0.14em",
          padding: "3px 10px",
          borderRadius: 999,
          background: "rgba(240,169,74,0.10)",
          border: `1px solid rgba(240,169,74,0.24)`,
          color: "rgba(240,169,74,0.85)",
        }}
      >
        {copy.badge}
      </span>

      <h2
        style={{
          fontFamily: displayFont,
          fontWeight: 600,
          fontSize: "clamp(1.7rem, 3.4vw, 2.5rem)",
          lineHeight: 1.15,
          marginTop: 18,
          marginBottom: 10,
          maxWidth: "22ch",
        }}
      >
        {copy.heading}
      </h2>
      <p style={{ fontFamily: bodyFont, color: ink45, fontSize: "0.98rem", maxWidth: "50ch", marginBottom: 48 }}>
        {copy.subtext}
      </p>

      {/* Rail of stops */}
      <div style={{ position: "relative", marginBottom: 40 }}>
        <div
          aria-hidden
          style={{
            position: "absolute",
            top: 17,
            insetInlineStart: 17,
            insetInlineEnd: 17,
            height: 2,
            background: hairline,
            zIndex: 0,
          }}
        />
        <div
          aria-hidden
          style={{
            position: "absolute",
            top: 17,
            insetInlineStart: 17,
            height: 2,
            background: `linear-gradient(90deg, ${gold}, ${teal})`,
            zIndex: 1,
            width: `calc((100% - 34px) * ${active / (steps.length - 1)})`,
            transition: reduce ? "none" : "width 0.5s cubic-bezier(0.16,1,0.3,1)",
          }}
        />
        <div style={{ position: "relative", zIndex: 2, display: "flex", justifyContent: "space-between" }}>
          {steps.map((s, i) => {
            const Icon = STEP_ICONS[i];
            const isActive = i === active;
            const isPast = i < active;
            return (
              <button
                key={s.label}
                onClick={() => jumpTo(i)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 8,
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: 0,
                  width: `${100 / steps.length}%`,
                }}
                aria-current={isActive ? "step" : undefined}
                aria-label={s.label}
              >
                <span
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: isActive ? gold : isPast ? "rgba(111,233,208,0.16)" : surface,
                    border: `1px solid ${isActive ? gold : isPast ? "rgba(111,233,208,0.4)" : hairline}`,
                    color: isActive ? navy : isPast ? teal : ink45,
                    transition: reduce ? "none" : "all 0.35s ease",
                    flexShrink: 0,
                  }}
                >
                  <Icon size={15} strokeWidth={2} />
                </span>
                <span
                  style={{ fontFamily: bodyFont, fontSize: 11.5, color: isActive ? "white" : ink25 }}
                  className="hidden sm:block"
                >
                  {s.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Active panel */}
      <div
        style={{
          borderRadius: 20,
          border: `1px solid ${hairline}`,
          background: "linear-gradient(180deg, rgba(23,28,58,0.72) 0%, rgba(13,16,38,0.6) 100%)",
          padding: "32px 28px",
          minHeight: 168,
        }}
      >
        <AnimatePresence mode="wait">
          {!isOutcome ? (
            <motion.div
              key={active}
              initial={reduce ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? {} : { opacity: 0, y: -10 }}
              transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
              style={{ display: "flex", alignItems: "center", gap: 20 }}
            >
              <span
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: 14,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "rgba(240,169,74,0.10)",
                  border: "1px solid rgba(240,169,74,0.24)",
                  color: gold,
                  flexShrink: 0,
                }}
              >
                <ActiveIcon size={24} strokeWidth={1.75} />
              </span>
              <div>
                <div style={{ fontFamily: displayFont, fontWeight: 600, fontSize: "1.15rem" }}>
                  {steps[active].label}
                </div>
                <div style={{ fontFamily: bodyFont, color: ink45, fontSize: "0.92rem", marginTop: 4 }}>
                  {steps[active].detail}
                </div>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="outcome"
              initial={reduce ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? {} : { opacity: 0, y: -10 }}
              transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
              className="grid grid-cols-1 sm:grid-cols-3 gap-4"
            >
              <OutcomeChip icon={CheckCircle2} tone={teal} {...copy.outcomes.completion} />
              <OutcomeChip icon={HelpCircle} tone={gold} {...copy.outcomes.uncertainty} />
              <OutcomeChip icon={RefreshCcw} tone={indigo} {...copy.outcomes.recovery} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}

function OutcomeChip({
  icon: Icon,
  tone,
  label,
  detail,
}: {
  icon: typeof CheckCircle2;
  tone: string;
  label: string;
  detail: string;
}) {
  return (
    <div
      style={{
        borderRadius: 14,
        border: `1px solid ${hairline}`,
        background: "rgba(255,255,255,0.02)",
        padding: "16px 16px",
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
      }}
    >
      <span style={{ color: tone, flexShrink: 0, marginTop: 2 }}>
        <Icon size={18} strokeWidth={2} />
      </span>
      <div>
        <div style={{ fontWeight: 600, fontSize: "0.92rem" }}>{label}</div>
        <div style={{ color: ink45, fontSize: "0.84rem", marginTop: 2, lineHeight: 1.45 }}>{detail}</div>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   CLOSING — short, centered, single repeated CTA. No new intent, no strip.
   ════════════════════════════════════════════════════════════════════════ */

function Closing({
  rtl,
  reduce,
  copy,
  displayFont,
  bodyFont,
}: {
  rtl: boolean;
  reduce: boolean;
  copy: (typeof RICO_ASCENT_COPY)["en"]["closing"];
  displayFont: string;
  bodyFont: string;
}) {
  return (
    <section
      style={{
        borderTop: `1px solid ${hairline}`,
        padding: "80px 20px 96px",
        textAlign: "center",
      }}
    >
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 14 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.4 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        style={{ maxWidth: 560, margin: "0 auto" }}
      >
        <h2
          style={{
            fontFamily: displayFont,
            fontWeight: 600,
            fontSize: "clamp(1.6rem, 3vw, 2.1rem)",
            lineHeight: 1.2,
            margin: 0,
          }}
        >
          {copy.headline}
        </h2>
        <p style={{ fontFamily: bodyFont, color: ink45, fontSize: "0.98rem", marginTop: 14 }}>{copy.subtext}</p>
        <a
          href="/command"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            marginTop: 30,
            padding: "13px 26px",
            borderRadius: 999,
            background: gold,
            color: navy,
            fontWeight: 600,
            fontSize: "0.95rem",
            textDecoration: "none",
            fontFamily: bodyFont,
            whiteSpace: "nowrap",
          }}
        >
          {copy.cta}
          <ArrowUpRight size={17} strokeWidth={2.25} style={rtl ? { transform: "scaleX(-1)" } : undefined} />
        </a>
      </motion.div>
    </section>
  );
}
