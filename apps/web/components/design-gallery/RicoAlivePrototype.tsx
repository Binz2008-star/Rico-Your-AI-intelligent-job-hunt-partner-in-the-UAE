"use client";

/**
 * DESIGN GALLERY PROTOTYPE — RicoAlivePrototype
 *
 * Standalone component for /design-gallery only.
 * NOT linked from production navigation.
 * NOT the homepage. NOT /command.
 * ALL data shown is SAMPLE / DEMO — no real AI calls, no real jobs, no real users.
 * No provider names exposed. No private chain-of-thought.
 *
 * Explores: AI thinking states, job intelligence cards, safety checkpoint,
 * animated chat thread, bilingual EN/AR, 3D-CSS depth, reduced-motion support.
 *
 * Stack: framer-motion@12.40.0 + Tailwind/CSS + Nocturne tokens. Zero new packages.
 */

import React from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

type Scene = "thinking" | "cards" | "safety" | "thread" | "stats";
type Lang = "en" | "ar";

/* ─── Shared helpers ─────────────────────────────────────────────────────── */

const gold = "rgb(240 169 74)";
const aura = "rgb(111 233 208)";
const indigo = "rgb(129 140 248)";
const navy = "#0b0d1c";

const glassStyle: React.CSSProperties = {
  background: "linear-gradient(180deg, rgba(23,28,58,0.80) 0%, rgba(13,16,38,0.72) 100%)",
  border: "1px solid rgba(255,255,255,0.09)",
  borderRadius: 20,
  boxShadow: "0 16px 48px rgba(5,6,18,0.24), inset 0 1px 0 rgba(255,255,255,0.06)",
  backdropFilter: "blur(32px)",
};

function GlassCard({ children, className = "", style }: { children: React.ReactNode; className?: string; style?: React.CSSProperties }) {
  return (
    <div className={className} style={{ ...glassStyle, ...style }}>
      {children}
    </div>
  );
}

function SimBadge() {
  return (
    <span style={{
      fontSize: 9, fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.14em",
      padding: "2px 8px", borderRadius: 999, background: "rgba(240,169,74,0.10)",
      border: "1px solid rgba(240,169,74,0.22)", color: "rgba(240,169,74,0.8)", flexShrink: 0
    }}>
      Sample data
    </span>
  );
}

function ROrb({ pulse, reduce }: { pulse?: boolean; reduce: boolean }) {
  return (
    <div style={{ position: "relative", flexShrink: 0 }}>
      <motion.div
        animate={pulse && !reduce ? { scale: [1, 1.07, 1] } : {}}
        transition={{ repeat: Infinity, duration: 2.2, ease: "easeInOut" }}
        style={{
          width: 32, height: 32, borderRadius: 999, display: "flex", alignItems: "center",
          justifyContent: "center", fontWeight: 700, fontSize: 12, color: "#0a0a0f",
          background: "radial-gradient(circle at 38% 32%, rgb(255 196 110), rgb(240 169 74))",
          boxShadow: "0 0 20px rgba(240,169,74,0.30), inset 0 1px 0 rgba(255,255,255,0.22)"
        }}>
        R
      </motion.div>
      {pulse && !reduce && (
        <motion.div animate={{ scale: [1, 1.8], opacity: [0.45, 0] }}
          transition={{ repeat: Infinity, duration: 1.8, ease: "easeOut" }}
          style={{
            position: "absolute", inset: 0, borderRadius: 999,
            border: "1.5px solid rgba(240,169,74,0.35)", pointerEvents: "none"
          }} />
      )}
    </div>
  );
}

/* ─── Scene: Thinking State ──────────────────────────────────────────────── */

const TOOL_STEPS = [
  { label: { en: "Reading your profile", ar: "قراءة ملفك الشخصي" }, state: "done" },
  { label: { en: "Scanning job market", ar: "فحص سوق العمل" }, state: "done" },
  { label: { en: "Scoring match quality", ar: "تقييم جودة التطابق" }, state: "active" },
  { label: { en: "Checking application history", ar: "التحقق من تاريخ الطلبات" }, state: "pending" },
  { label: { en: "Drafting recommendation", ar: "صياغة التوصية" }, state: "pending" },
] as const;

const PHRASES = {
  en: ["Reviewing your career goals", "Analysing UAE market conditions", "Comparing skills to role requirements"],
  ar: ["مراجعة أهدافك المهنية", "تحليل ظروف السوق في الإمارات", "مقارنة مهاراتك بمتطلبات الدور"],
};

const stateColor: Record<string, string> = { done: aura, active: gold, pending: "rgba(255,255,255,0.18)" };
const stateIconEl: Record<string, React.ReactNode> = {
  done: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M20 6L9 17l-5-5"/></svg>,
  active: <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="4" fill="currentColor"/><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" fill="none"/></svg>,
  pending: <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" fill="none"/></svg>,
};

function ThinkingScene({ lang, reduce }: { lang: Lang; reduce: boolean }) {
  const [pi, setPi] = useState(0);
  const [dots, setDots] = useState(".");
  const phrases = PHRASES[lang];

  useEffect(() => {
    if (reduce) return;
    const a = setInterval(() => setPi(i => (i + 1) % phrases.length), 2800);
    const b = setInterval(() => setDots(d => d.length >= 3 ? "." : d + "."), 420);
    return () => { clearInterval(a); clearInterval(b); };
  }, [reduce, phrases.length]);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      {/* Orb + phrase */}
      <GlassCard style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <ROrb pulse reduce={reduce} />
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.14em" }}>
              {lang === "ar" ? "يعالج" : "Processing"}
            </span>
            <AnimatePresence mode="wait">
              <motion.p key={pi}
                initial={reduce ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduce ? {} : { opacity: 0, y: -5 }}
                transition={{ duration: 0.26 }}
                style={{ fontSize: 13, color: "rgba(255,255,255,0.9)", fontWeight: 500, lineHeight: 1.4 }}>
                {phrases[pi]}
              </motion.p>
            </AnimatePresence>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[80, 60, 90, 45].map((w, i) => (
            <motion.div key={i} initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }}
              transition={{ delay: i * 0.08 }}
              className={reduce ? undefined : "rico-chat-shimmer"}
              style={{ height: 9, borderRadius: 6, width: `${w}%` }} />
          ))}
        </div>
      </GlassCard>

      {/* Tool rail */}
      <GlassCard style={{ padding: 24 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <span style={{ fontSize: 10, color: "rgba(255,255,255,0.30)", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.14em" }}>
            {lang === "ar" ? "سجل النشاط" : "Activity Rail"}
          </span>
          <SimBadge />
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          {TOOL_STEPS.map((step, i) => (
            <motion.div key={i}
              initial={reduce ? false : { opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08, duration: 0.28 }}
              style={{
                display: "flex", alignItems: "flex-start", gap: 10, paddingBlock: 10,
                borderBottom: i < TOOL_STEPS.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none"
              }}>
              <motion.span
                animate={step.state === "active" && !reduce ? { scale: [1, 1.2, 1] } : {}}
                transition={{ repeat: Infinity, duration: 1.6 }}
                style={{ color: stateColor[step.state], lineHeight: 1, marginTop: 1, flexShrink: 0, display: "flex" }}>
                {stateIconEl[step.state]}
              </motion.span>
              <span style={{ fontSize: 12, color: step.state === "pending" ? "rgba(255,255,255,0.22)" : "rgba(255,255,255,0.80)", lineHeight: 1.4 }}>
                {step.label[lang]}
                {step.state === "active" && <span style={{ color: "rgba(255,255,255,0.35)" }}>{dots}</span>}
              </span>
            </motion.div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}

/* ─── Scene: Job Intelligence Cards ─────────────────────────────────────── */

const JOBS = [
  {
    id: "j1", title: { en: "Senior Product Manager", ar: "مدير منتج أول" },
    company: "Noon", location: { en: "Dubai, UAE", ar: "دبي، الإمارات" },
    score: 91, tier: "Strong", tierAr: "تطابق قوي", tierColor: aura,
    reasons: {
      en: ["5+ yrs PM experience", "UAE e-commerce background", "Arabic fluency required"],
      ar: ["5+ سنوات خبرة إدارة منتج", "خلفية تجارة إلكترونية UAE", "إتقان العربية مطلوب"]
    },
    salary: "AED 32,000–42,000/mo"
  },
  {
    id: "j2", title: { en: "Engineering Manager", ar: "مدير هندسي" },
    company: "Careem", location: { en: "Abu Dhabi", ar: "أبوظبي" },
    score: 74, tier: "Good", tierAr: "تطابق جيد", tierColor: gold,
    reasons: { en: ["Team leadership match", "Backend systems relevant"], ar: ["خبرة قيادة الفريق", "أنظمة الخلفية ذات صلة"] },
    salary: "AED 25,000–33,000/mo"
  },
  {
    id: "j3", title: { en: "Head of Growth", ar: "رئيس قسم النمو" },
    company: "Tabby", location: { en: "Dubai, UAE", ar: "دبي" },
    score: 58, tier: "Possible", tierAr: "محتمل", tierColor: indigo,
    reasons: { en: ["Growth marketing transferable"], ar: ["تسويق النمو قابل للتحويل"] },
    salary: "AED 22,000–28,000/mo"
  },
];

const RING_R = 26;
const RING_C = 2 * Math.PI * RING_R;

function ScoreRing({ score, color, reduce }: { score: number; color: string; reduce: boolean }) {
  const off = RING_C * (1 - score / 100);
  return (
    <svg width="70" height="70" viewBox="0 0 70 70" aria-label={`${score}% match`} role="img">
      <circle cx="35" cy="35" r={RING_R} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="5" />
      <motion.circle cx="35" cy="35" r={RING_R} fill="none" stroke={color} strokeWidth="5"
        strokeLinecap="round" strokeDasharray={RING_C}
        initial={{ strokeDashoffset: RING_C }}
        animate={{ strokeDashoffset: off }}
        transition={reduce ? { duration: 0 } : { duration: 1.1, ease: [0.16, 1, 0.3, 1], delay: 0.12 }}
        transform="rotate(-90 35 35)" />
      <text x="35" y="33" textAnchor="middle" dominantBaseline="central"
        fill={color} fontSize="13" fontWeight="700">{score}</text>
      <text x="35" y="44" textAnchor="middle" fill="rgba(255,255,255,0.30)" fontSize="8">%</text>
    </svg>
  );
}

function JobCard({ job, lang, reduce }: { job: typeof JOBS[0]; lang: Lang; reduce: boolean }) {
  const [open, setOpen] = useState(false);
  const [hov, setHov] = useState(false);
  return (
    <div style={{ perspective: 900 }}>
      <motion.div
        onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
        animate={hov && !reduce ? { rotateX: -2, rotateY: 3, scale: 1.01 } : { rotateX: 0, rotateY: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 200, damping: 24 }}
        style={{
          transformStyle: "preserve-3d",
          background: "linear-gradient(180deg,rgba(23,28,58,0.80) 0%,rgba(13,16,38,0.72) 100%)",
          border: "1px solid rgba(255,255,255,0.09)", borderRadius: 18,
          boxShadow: "0 12px 36px rgba(5,6,18,0.20)", overflow: "hidden"
        }}>
        <div style={{ padding: "18px 20px", display: "flex", alignItems: "flex-start", gap: 14 }}>
          <ScoreRing score={job.score} color={job.tierColor} reduce={reduce} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
              <div>
                <p style={{ fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.92)", lineHeight: 1.3 }}>{job.title[lang]}</p>
                <p style={{ fontSize: 11, color: "rgba(255,255,255,0.45)", marginTop: 2 }}>{job.company} · {job.location[lang]}</p>
              </div>
              <span style={{
                fontSize: 10, padding: "2px 9px", borderRadius: 999, fontWeight: 600, flexShrink: 0,
                background: `${job.tierColor.replace("rgb(", "rgba(").replace(")", ",0.12)")}`,
                border: `1px solid ${job.tierColor.replace("rgb(", "rgba(").replace(")", ",0.28)")}`,
                color: job.tierColor
              }}>
                {lang === "ar" ? job.tierAr : job.tier}
              </span>
            </div>
            <p style={{ fontSize: 10, color: "rgba(255,255,255,0.32)", marginTop: 6, fontFamily: "monospace", letterSpacing: "0.03em" }}>
              <span style={{ color: "rgba(255,255,255,0.18)", marginRight: 4 }}>＄</span>{job.salary}
            </p>
          </div>
        </div>
        <button onClick={() => setOpen(o => !o)}
          style={{
            width: "100%", padding: "10px 20px", display: "flex", alignItems: "center", justifyContent: "space-between",
            borderTop: "1px solid rgba(255,255,255,0.07)", border: "none",
            background: open ? "rgba(255,255,255,0.03)" : "transparent",
            cursor: "pointer", fontSize: 11, color: "rgba(255,255,255,0.42)",
            transition: "background 0.15s"
          }}
          aria-expanded={open}>
          <span>{lang === "ar" ? "لماذا هذا التطابق؟" : "Why this match?"}</span>
          <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.18 }} style={{ display: "flex" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6"/></svg>
          </motion.span>
        </button>
        <AnimatePresence>
          {open && (
            <motion.div initial={reduce ? false : { height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }} exit={reduce ? {} : { height: 0, opacity: 0 }}
              transition={{ duration: 0.26 }} style={{ overflow: "hidden" }}>
              <div style={{ padding: "8px 20px 18px", display: "flex", flexDirection: "column", gap: 6 }}>
                {job.reasons[lang].map((r, i) => (
                  <motion.div key={i} initial={reduce ? false : { opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}
                    style={{ display: "flex", gap: 8, fontSize: 12, color: "rgba(255,255,255,0.60)", alignItems: "flex-start" }}>
                    <span style={{ color: aura, flexShrink: 0, marginTop: 1 }}>✓</span>{r}
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

function CardsScene({ lang, reduce }: { lang: Lang; reduce: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.14em" }}>
          {lang === "ar" ? "ذكاء الوظائف" : "Job Intelligence"}
        </span>
        <SimBadge />
      </div>
      {JOBS.map((job, i) => (
        <motion.div key={job.id} initial={reduce ? false : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1, duration: 0.32 }}>
          <JobCard job={job} lang={lang} reduce={reduce} />
        </motion.div>
      ))}
    </div>
  );
}

/* ─── Scene: Safety Checkpoint ───────────────────────────────────────────── */

type Gate = "pending" | "approved" | "declined";

function SafetyScene({ lang, reduce }: { lang: Lang; reduce: boolean }) {
  const [gate, setGate] = useState<Gate>("pending");
  return (
    <div style={{ maxWidth: 560, margin: "0 auto", display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.14em" }}>
          {lang === "ar" ? "نقطة التحقق الأمنية" : "Safety Checkpoint"}
        </span>
        <SimBadge />
      </div>
      <GlassCard style={{ overflow: "hidden" }}>
        {/* Header */}
        <div style={{ padding: "16px 20px", borderBottom: "1px solid rgba(255,255,255,0.07)", display: "flex", gap: 12, alignItems: "center" }}>
          <motion.div animate={gate === "pending" && !reduce ? { scale: [1, 1.1, 1] } : {}}
            transition={{ repeat: Infinity, duration: 2 }}
            style={{
              width: 32, height: 32, borderRadius: 999, display: "flex", alignItems: "center", justifyContent: "center",
              background: gate === "approved" ? "rgba(16,185,129,0.15)" : gate === "declined" ? "rgba(255,255,255,0.06)" : "rgba(240,169,74,0.12)",
              border: `1px solid ${gate === "approved" ? "rgba(16,185,129,0.30)" : gate === "declined" ? "rgba(255,255,255,0.10)" : "rgba(240,169,74,0.28)"}`,
              fontSize: 16
            }}>
            {gate === "approved" ? "✓" : gate === "declined" ? "✕" : "◈"}
          </motion.div>
          <div>
            <p style={{ fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.90)" }}>
              {gate === "approved" ? (lang === "ar" ? "تمت الموافقة" : "Approved") :
                gate === "declined" ? (lang === "ar" ? "تم الرفض" : "Declined") :
                  (lang === "ar" ? "يلزم تأكيدك قبل المتابعة" : "Your confirmation required")}
            </p>
            <p style={{ fontSize: 11, color: "rgba(255,255,255,0.30)", marginTop: 2 }}>
              {gate === "pending" ? (lang === "ar" ? "إجراء عالي التأثير" : "High-impact action") :
                gate === "approved" ? (lang === "ar" ? "تمت المعالجة" : "Processed") : (lang === "ar" ? "جلستك آمنة" : "Session safe")}
            </p>
          </div>
        </div>
        {/* Rico message */}
        <div style={{ padding: "14px 20px", borderBottom: "1px solid rgba(255,255,255,0.07)", display: "flex", gap: 10 }}>
          <ROrb pulse={false} reduce={reduce} />
          <p style={{ fontSize: 12, color: "rgba(255,255,255,0.55)", lineHeight: 1.6 }} dir={lang === "ar" ? "rtl" : "ltr"}>
            {lang === "ar"
              ? "قبل أن أتخذ هذا الإجراء نيابةً عنك، أحتاج إلى موافقتك الصريحة. هذا إجراء في العالم الحقيقي."
              : "Before I take this action on your behalf, I need your explicit approval. This is a real-world action."}
          </p>
        </div>
        {/* Summary */}
        <div style={{ padding: "14px 20px", borderBottom: "1px solid rgba(255,255,255,0.07)", display: "flex", flexDirection: "column", gap: 8 }}>
          {[
            { k: { en: "Action", ar: "الإجراء" }, v: { en: "Submit application", ar: "إرسال طلب التوظيف" }, hi: true },
            { k: { en: "Role", ar: "الوظيفة" }, v: { en: "Senior Product Manager", ar: "مدير منتج أول" } },
            { k: { en: "Match", ar: "التطابق" }, v: { en: "91%", ar: "٩١٪" }, hi: true },
          ].map((row, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
              <span style={{ color: "rgba(255,255,255,0.35)" }}>{row.k[lang]}</span>
              <span style={{ fontWeight: 500, color: row.hi ? gold : "rgba(255,255,255,0.80)" }}>{row.v[lang]}</span>
            </div>
          ))}
        </div>
        {/* Buttons / result */}
        <AnimatePresence mode="wait">
          {gate === "pending" ? (
            <motion.div key="btns" initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              style={{ padding: "14px 20px", display: "flex", gap: 10 }}>
              <button onClick={() => setGate("approved")}
                style={{
                  flex: 1, padding: "11px 0", borderRadius: 12, fontSize: 12, fontWeight: 600, cursor: "pointer",
                  background: "rgba(16,185,129,0.16)", border: "1px solid rgba(16,185,129,0.38)", color: "rgb(16,185,129)",
                  boxShadow: "0 0 18px rgba(16,185,129,0.12)", transition: "box-shadow 0.15s, background 0.15s"
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(16,185,129,0.24)"; (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 24px rgba(16,185,129,0.22)"; }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(16,185,129,0.16)"; (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 18px rgba(16,185,129,0.12)"; }}>
                {lang === "ar" ? "نعم، وافق" : "Yes, approve"}
              </button>
              <button onClick={() => setGate("declined")}
                style={{
                  flex: 1, padding: "11px 0", borderRadius: 12, fontSize: 12, cursor: "pointer",
                  background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.12)", color: "rgba(255,255,255,0.50)",
                  transition: "background 0.15s"
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.08)"; }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.04)"; }}>
                {lang === "ar" ? "لا، أوقف" : "No, cancel"}
              </button>
            </motion.div>
          ) : (
            <motion.div key="result" initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
              style={{ padding: "14px 20px" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                <motion.div
                  initial={reduce ? false : { scale: 0.5, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: "spring", stiffness: 280, damping: 22 }}
                  style={{
                    width: 28, height: 28, borderRadius: 999, flexShrink: 0,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    background: gate === "approved" ? "rgba(16,185,129,0.20)" : "rgba(255,255,255,0.06)",
                    border: gate === "approved" ? "1px solid rgba(16,185,129,0.40)" : "1px solid rgba(255,255,255,0.12)",
                    color: gate === "approved" ? "rgb(16,185,129)" : "rgba(255,255,255,0.40)"
                  }}>
                  {gate === "approved"
                    ? <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M20 6L9 17l-5-5"/></svg>
                    : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>}
                </motion.div>
                <p style={{ fontSize: 12, color: "rgba(255,255,255,0.55)", lineHeight: 1.6, paddingTop: 4 }}>
                  {gate === "approved"
                    ? (lang === "ar" ? "تمت الموافقة. سأعلمك بالتقدم." : "Approved. I will keep you updated on progress.")
                    : (lang === "ar" ? "تم الإلغاء. لا إجراء اتُّخذ." : "Cancelled. No action taken.")}
                </p>
              </div>
              <button onClick={() => setGate("pending")}
                style={{
                  marginTop: 10, fontSize: 11, color: "rgba(255,255,255,0.22)", background: "none", border: "none",
                  cursor: "pointer", textDecoration: "underline", textUnderlineOffset: 2, padding: 0
                }}>
                {lang === "ar" ? "إعادة تشغيل العرض" : "Reset demo"}
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </GlassCard>
    </div>
  );
}

/* ─── Scene: Chat Thread ─────────────────────────────────────────────────── */

const MESSAGES = [
  { id: 1, role: "user", en: "What's the best PM role for me in the UAE right now?", ar: "ما أفضل دور لمدير منتج مناسب لي في الإمارات الآن؟" },
  { id: 2, role: "rico", en: "Let me check your profile and today's market.", ar: "دعني أطلع على ملفك الشخصي وسوق اليوم.", activity: { en: "Profile + market scan", ar: "قراءة الملف + فحص السوق" } },
  { id: 3, role: "rico", en: "Found 4 strong matches. Top pick: Senior PM at Noon — 91% match based on your e-commerce background and Arabic fluency.", ar: "وجدت 4 تطابقات قوية. الأول: مدير منتج أول في نون — 91% تطابق بناءً على خلفيتك وإجادتك للعربية.", activity: { en: "Score analysis complete", ar: "اكتمل تحليل النتيجة" } },
  { id: 4, role: "user", en: "Have I applied to Noon before?", ar: "هل سبق أن تقدمت لنون؟" },
  { id: 5, role: "rico", en: "No prior applications to Noon found. Your last similar application was Careem in March 2025 — reached final interview. Want me to prepare a targeted application?", ar: "لا توجد طلبات سابقة لنون. آخر طلب مماثل كان كريم في مارس 2025 وصل للمقابلة النهائية. هل أعد طلباً مخصصاً؟", activity: { en: "Application history checked", ar: "تم التحقق من التاريخ" } },
];

function ChatScene({ lang, reduce }: { lang: Lang; reduce: boolean }) {
  const [thinking, setThinking] = useState(false);
  const [dots, setDots] = useState(1);

  useEffect(() => {
    if (!thinking || reduce) return;
    const iv = setInterval(() => setDots(d => d >= 3 ? 1 : d + 1), 380);
    return () => clearInterval(iv);
  }, [thinking, reduce]);

  const simulate = () => {
    setThinking(true);
    setTimeout(() => setThinking(false), 2600);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.14em" }}>
          {lang === "ar" ? "المحادثة" : "Chat Thread"}
        </span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <SimBadge />
          <button onClick={simulate}
            style={{
              fontSize: 10, padding: "3px 10px", borderRadius: 999, background: "transparent",
              border: "1px solid rgba(255,255,255,0.12)", color: "rgba(255,255,255,0.35)", cursor: "pointer"
            }}>
            {lang === "ar" ? "محاكاة التفكير" : "Simulate thinking"}
          </button>
        </div>
      </div>
      <GlassCard style={{ overflow: "hidden" }}>
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14, maxHeight: 400, overflowY: "auto" }}>
          {MESSAGES.map((msg, i) => (
            <motion.div key={msg.id}
              initial={reduce ? false : { opacity: 0, y: 10, x: msg.role === "user" ? 8 : -8 }}
              whileInView={{ opacity: 1, y: 0, x: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ delay: i * 0.06, duration: 0.28 }}
              style={{ display: "flex", flexDirection: msg.role === "user" ? "row-reverse" : "row", gap: 10, alignItems: "flex-start" }}
              dir={lang === "ar" ? "rtl" : "ltr"}>
              {msg.role === "rico" && <ROrb pulse={false} reduce={reduce} />}
              <div style={{
                display: "flex", flexDirection: "column", gap: 4, maxWidth: "70%",
                alignItems: msg.role === "user" ? "flex-end" : "flex-start"
              }}>
                {msg.activity && (
                  <span style={{
                    fontSize: 9, padding: "2px 8px", borderRadius: 999, fontFamily: "monospace",
                    background: "rgba(111,233,208,0.10)", border: "1px solid rgba(111,233,208,0.22)", color: "rgba(111,233,208,0.75)"
                  }}>
                    ◉ {msg.activity[lang]}
                  </span>
                )}
                <div style={{
                  padding: "10px 14px", lineHeight: 1.65,
                  borderRadius: msg.role === "user" ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
                  fontSize: 12,
                  background: msg.role === "user"
                    ? "rgba(255,255,255,0.07)"
                    : "linear-gradient(160deg, rgba(23,28,58,0.92) 0%, rgba(17,22,48,0.88) 100%)",
                  border: msg.role === "rico"
                    ? "1px solid rgba(240,169,74,0.14)"
                    : "1px solid rgba(255,255,255,0.09)",
                  color: "rgba(255,255,255,0.84)",
                  boxShadow: msg.role === "rico" ? "0 4px 16px rgba(5,6,18,0.20)" : "none"
                }}>
                  {msg[lang]}
                </div>
              </div>
            </motion.div>
          ))}
          <AnimatePresence>
            {thinking && (
              <motion.div key="thinking"
                initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <ROrb pulse reduce={reduce} />
                <div style={{
                  padding: "10px 14px", borderRadius: 14, fontSize: 12, color: "rgba(255,255,255,0.40)",
                  background: "rgba(23,28,58,0.90)", border: "1px solid rgba(255,255,255,0.09)"
                }}>
                  {lang === "ar" ? "يفكر" : "Thinking"}&nbsp;
                {[0, 1, 2].map(i => (
                  <motion.span key={i}
                    animate={reduce ? {} : { opacity: [0.2, 1, 0.2], y: [0, -3, 0] }}
                    transition={{ repeat: Infinity, duration: 1.2, delay: i * 0.18 }}
                    style={{ display: "inline-block", fontWeight: 700, color: gold }}>
                    •
                  </motion.span>
                ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        {/* Input — never animated, mobile-safe */}
        <div style={{
          borderTop: "1px solid rgba(255,255,255,0.07)", padding: "10px 16px",
          display: "flex", gap: 10, alignItems: "center",
          background: "rgba(255,255,255,0.015)"
        }}>
          <input readOnly type="text"
            placeholder={lang === "ar" ? "اكتب رسالتك… (عرض تجريبي)" : "Type your message… (demo)"}
            dir={lang === "ar" ? "rtl" : "ltr"}
            style={{
              flex: 1, background: "transparent", border: "none", outline: "none", fontSize: 12,
              color: "rgba(255,255,255,0.46)", fontFamily: "inherit", caretColor: gold
            }} />
          <motion.button
            whileHover={{ scale: 1.08, boxShadow: "0 0 18px rgba(240,169,74,0.35)" }}
            whileTap={{ scale: 0.94 }}
            style={{
              width: 32, height: 32, borderRadius: 999, border: "1px solid rgba(240,169,74,0.40)",
              background: "rgba(240,169,74,0.14)", color: gold, cursor: "pointer", fontSize: 13,
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0
            }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
          </motion.button>
        </div>
      </GlassCard>
    </div>
  );
}

/* ─── Scene: Dashboard Stats ────────────────────────────────────────────── */

const STATS = [
  { en: "Applications sent",    ar: "الطلبات المرسلة",     value: 24,  suffix: "",   color: aura,   icon: "✉" },
  { en: "Interviews landed",    ar: "المقابلات المحصودة",  value: 6,   suffix: "",   color: gold,   icon: "🎤" },
  { en: "Avg match score",      ar: "متوسط نسبة التطابق",  value: 82,  suffix: "%",  color: indigo, icon: "◎" },
  { en: "CV views this week",   ar: "مشاهدات السيرة الذاتية", value: 41, suffix: "",  color: "rgb(248,113,113)", icon: "👁" },
];

function AnimatedNumber({ to, reduce }: { to: number; reduce: boolean }) {
  const [val, setVal] = React.useState(0);
  React.useEffect(() => {
    if (reduce) { setVal(to); return; }
    let start = 0;
    const step = Math.ceil(to / 28);
    const iv = setInterval(() => {
      start = Math.min(start + step, to);
      setVal(start);
      if (start >= to) clearInterval(iv);
    }, 36);
    return () => clearInterval(iv);
  }, [to, reduce]);
  return <span>{val}</span>;
}

function StatsScene({ lang, reduce }: { lang: Lang; reduce: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.14em" }}>
          {lang === "ar" ? "لمحة إحصائية" : "Dashboard at a glance"}
        </span>
        <SimBadge />
      </div>
      {/* KPI grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {STATS.map((stat, i) => (
          <motion.div key={i}
            initial={reduce ? false : { opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.09, duration: 0.38, ease: [0.22, 0.61, 0.36, 1] }}>
            <GlassCard style={{ padding: "18px 20px", position: "relative", overflow: "hidden" }}>
              {/* ambient tint */}
              <div style={{
                position: "absolute", inset: 0,
                background: `radial-gradient(ellipse at 80% 20%, ${stat.color.replace("rgb(", "rgba(").replace(")", ",0.07)")} 0%, transparent 65%)`,
                pointerEvents: "none"
              }} />
              <div style={{ fontSize: 18, marginBottom: 10 }}>{stat.icon}</div>
              <p style={{ fontSize: 28, fontWeight: 700, lineHeight: 1, color: stat.color, fontFamily: "monospace" }}>
                <AnimatedNumber to={stat.value} reduce={reduce} />{stat.suffix}
              </p>
              <p style={{ fontSize: 11, color: "rgba(255,255,255,0.38)", marginTop: 6 }}>
                {lang === "ar" ? stat.ar : stat.en}
              </p>
            </GlassCard>
          </motion.div>
        ))}
      </div>
      {/* Mini pipeline bar */}
      <GlassCard style={{ padding: "16px 20px" }}>
        <p style={{ fontSize: 10, color: "rgba(255,255,255,0.28)", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.14em", marginBottom: 12 }}>
          {lang === "ar" ? "مسار الطلبات" : "Application pipeline"}
        </p>
        {[
          { en: "Applied", ar: "مرسل", v: 24, color: aura },
          { en: "Screening", ar: "فرز", v: 11, color: gold },
          { en: "Interview", ar: "مقابلة", v: 6, color: indigo },
          { en: "Offer", ar: "عرض", v: 2, color: "rgb(248,113,113)" },
        ].map((row, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", width: 62, flexShrink: 0 }}>
              {lang === "ar" ? row.ar : row.en}
            </span>
            <div style={{ flex: 1, height: 6, borderRadius: 999, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${(row.v / 24) * 100}%` }}
                transition={reduce ? { duration: 0 } : { duration: 0.7, delay: 0.2 + i * 0.1, ease: [0.16, 1, 0.3, 1] }}
                style={{ height: "100%", borderRadius: 999, background: row.color }} />
            </div>
            <span style={{ fontSize: 10, fontFamily: "monospace", color: row.color, width: 18, textAlign: "right", flexShrink: 0 }}>{row.v}</span>
          </div>
        ))}
      </GlassCard>
    </div>
  );
}

/* ─── Root component ─────────────────────────────────────────────────────── */

const SCENES: { key: Scene; en: string; ar: string }[] = [
  { key: "thinking", en: "AI Thinking", ar: "حالة التفكير" },
  { key: "cards", en: "Job Intelligence", ar: "ذكاء الوظائف" },
  { key: "safety", en: "Safety Gate", ar: "نقطة الأمان" },
  { key: "thread", en: "Chat Thread", ar: "المحادثة" },
  { key: "stats", en: "Dashboard Stats", ar: "إحصائيات" },
];

export default function RicoAlivePrototype() {
  const [scene, setScene] = useState<Scene>("thinking");
  const [lang, setLang] = useState<Lang>("en");
  const reduce = useReducedMotion() ?? false;

  /* Inject keyframes once */
  if (typeof document !== "undefined" && !document.getElementById("rico-alive-kf")) {
    const st = document.createElement("style");
    st.id = "rico-alive-kf";
    st.textContent = `
      @keyframes shimmer { 0%,100%{background-position:200% 0} 50%{background-position:0% 0} }
      @keyframes rico-pulse { 0%,100%{opacity:.65;transform:scale(1)} 50%{opacity:1;transform:scale(1.035)} }
      @keyframes rico-float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
      .rico-orb-ring { animation: rico-pulse 2.4s ease-in-out infinite; }
      .rico-chat-shimmer { background: linear-gradient(90deg,rgba(255,255,255,0.04) 0%,rgba(255,255,255,0.10) 50%,rgba(255,255,255,0.04) 100%); background-size:200% 100%; animation: shimmer 1.7s ease-in-out infinite; }
    `;
    document.head.appendChild(st);
  }

  return (
    <div style={{ minHeight: "100vh", background: navy, color: "rgba(255,255,255,0.88)", fontFamily: "var(--font-body, system-ui, sans-serif)", position: "relative", overflowX: "hidden" }}>
      {/* Ambient glows */}
      <div aria-hidden style={{ pointerEvents: "none", position: "fixed", inset: 0, overflow: "hidden" }}>
        {/* Top-left ember */}
        <div style={{
          position: "absolute", top: -200, left: -200, width: 700, height: 700, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(240,169,74,0.07) 0%, transparent 65%)", filter: "blur(90px)"
        }} />
        {/* Bottom-right indigo */}
        <div style={{
          position: "absolute", bottom: -200, right: -200, width: 600, height: 600, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(129,140,248,0.06) 0%, transparent 65%)", filter: "blur(110px)"
        }} />
        {/* Center-screen aura whisper */}
        <div style={{
          position: "absolute", top: "40%", left: "50%", transform: "translate(-50%,-50%)",
          width: 400, height: 400, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(111,233,208,0.03) 0%, transparent 70%)", filter: "blur(70px)"
        }} />
      </div>

      {/* Header */}
      <div style={{
        position: "sticky", top: 0, zIndex: 40, backdropFilter: "blur(28px)",
        background: "rgba(11,13,28,0.92)",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        boxShadow: "0 1px 0 rgba(240,169,74,0.08)",
        padding: "10px 24px", display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* Orb with glow */}
          <div style={{ position: "relative", flexShrink: 0 }}>
            <div style={{
              width: 30, height: 30, borderRadius: 999,
              background: "radial-gradient(circle at 38% 34%, rgb(255 196 110), rgb(240 169 74))",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 11, fontWeight: 700, color: "#0a0a0f",
              boxShadow: "0 0 16px rgba(240,169,74,0.40), inset 0 1px 0 rgba(255,255,255,0.22)"
            }}>R</div>
          </div>
          <div>
            <span style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.015em", color: "rgba(255,255,255,0.92)" }}>
              {lang === "ar" ? "ريكو — مفهوم تصميمي" : "Rico Command"}
            </span>
            <span style={{
              marginLeft: 8, fontSize: 9, fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.14em",
              padding: "1px 7px", borderRadius: 999, background: "rgba(240,169,74,0.10)",
              border: "1px solid rgba(240,169,74,0.22)", color: "rgba(240,169,74,0.8)", verticalAlign: "middle"
            }}>Concept</span>
          </div>
        </div>
        <div style={{ flex: 1 }} />
        {/* Scene tabs */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {SCENES.map(s => (
            <button key={s.key} onClick={() => setScene(s.key)}
              style={{
                fontSize: 11, padding: "4px 14px", borderRadius: 999, cursor: "pointer",
                transition: "background 0.14s, color 0.14s, border-color 0.14s, box-shadow 0.14s",
                border: scene === s.key ? "1px solid rgba(240,169,74,0.40)" : "1px solid rgba(255,255,255,0.09)",
                background: scene === s.key ? "rgba(240,169,74,0.13)" : "transparent",
                color: scene === s.key ? gold : "rgba(255,255,255,0.38)",
                fontWeight: scene === s.key ? 600 : 400,
                boxShadow: scene === s.key ? "0 0 12px rgba(240,169,74,0.15)" : "none"
              }}>
              {s[lang]}
            </button>
          ))}
        </div>
        {/* Lang toggle */}
        <button onClick={() => setLang(l => l === "en" ? "ar" : "en")}
          style={{
            fontSize: 11, padding: "4px 12px", borderRadius: 999, cursor: "pointer",
            border: "1px solid rgba(255,255,255,0.12)", background: "transparent", color: "rgba(255,255,255,0.45)"
          }}>
          {lang === "en" ? "عربي" : "EN"}
        </button>
      </div>

      {/* Stage */}
      <div style={{ padding: "28px 24px 40px", maxWidth: 900, margin: "0 auto" }} dir={lang === "ar" ? "rtl" : "ltr"}>
        <AnimatePresence mode="wait">
          <motion.div key={scene}
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? {} : { opacity: 0, y: -8 }}
            transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}>
            {scene === "thinking" && <ThinkingScene lang={lang} reduce={reduce} />}
            {scene === "cards" && <CardsScene lang={lang} reduce={reduce} />}
            {scene === "safety" && <SafetyScene lang={lang} reduce={reduce} />}
            {scene === "thread" && <ChatScene lang={lang} reduce={reduce} />}
            {scene === "stats" && <StatsScene lang={lang} reduce={reduce} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
