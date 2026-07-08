"use client";

/**
 * SANDBOX PROTOTYPE COMPONENT — ThinkingState
 * Simulates Rico's AI thinking state, tool activity rail, and visible safe-action progress.
 * ALL tool activity is DEMO/SIMULATED. No real AI calls are made here.
 */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

type StepState = "done" | "active" | "pending";

interface ToolStepDef {
  id: number;
  icon: string;
  label: string;
  detail: string;
  state: StepState;
  color: string;
}

const TOOL_STEPS_EN: ToolStepDef[] = [
  { id: 1, icon: "⬡", label: "Reading your profile", detail: "CV + preferences loaded", state: "done", color: "aura" },
  { id: 2, icon: "⬡", label: "Scanning job market", detail: "Checking 3 job feeds", state: "done", color: "aura" },
  { id: 3, icon: "⬡", label: "Scoring match quality", detail: "Running match analysis", state: "active", color: "gold" },
  { id: 4, icon: "⬡", label: "Checking application history", detail: "Pending", state: "pending", color: "surface" },
  { id: 5, icon: "⬡", label: "Drafting recommendation", detail: "Pending", state: "pending", color: "surface" },
];

const TOOL_STEPS_AR: ToolStepDef[] = [
  { id: 1, icon: "⬡", label: "قراءة ملفك الشخصي", detail: "تم تحميل السيرة الذاتية والتفضيلات", state: "done", color: "aura" },
  { id: 2, icon: "⬡", label: "فحص سوق العمل", detail: "جارٍ فحص 3 مصادر وظيفية", state: "done", color: "aura" },
  { id: 3, icon: "⬡", label: "تقييم جودة التطابق", detail: "جارٍ تشغيل تحليل التطابق", state: "active", color: "gold" },
  { id: 4, icon: "⬡", label: "التحقق من تاريخ الطلبات", detail: "في الانتظار", state: "pending", color: "surface" },
  { id: 5, icon: "⬡", label: "صياغة التوصية", detail: "في الانتظار", state: "pending", color: "surface" },
];

type ToolStep = ToolStepDef;

const stateColors: Record<StepState, string> = {
  done: "rgb(var(--aura))",
  active: "rgb(var(--gold))",
  pending: "rgb(var(--text-disabled))",
};

const stateIcons: Record<StepState, string> = {
  done: "✓",
  active: "◉",
  pending: "○",
};

function ToolStep({ step, index, reduce, lang }: { step: ToolStep; index: number; reduce: boolean; lang: "en" | "ar" }) {
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.32, delay: index * 0.08, ease: [0.16, 1, 0.3, 1] }}
      className="flex items-start gap-3 py-2.5"
    >
      {/* Connector line */}
      <div className="flex flex-col items-center shrink-0 mt-0.5" style={{ minWidth: 20 }}>
        <motion.span
          animate={step.state === "active" && !reduce ? { scale: [1, 1.2, 1] } : {}}
          transition={{ repeat: Infinity, duration: 1.6, ease: "easeInOut" }}
          style={{ color: stateColors[step.state], fontSize: 14, lineHeight: 1, fontWeight: 600 }}
        >
          {stateIcons[step.state]}
        </motion.span>
        {index < 4 && (
          <div className={[
            "w-px mt-1.5 flex-1",
            step.state === "done" ? "bg-[rgb(var(--aura)/0.35)]" : "bg-[rgb(var(--overlay)/0.08)]"
          ].join(" ")} style={{ height: 20 }} />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className={[
          "text-sm leading-snug",
          step.state === "pending" ? "text-[rgb(var(--text-disabled))]" : "text-[rgb(var(--text-primary))]"
        ].join(" ")}>
          {step.label}
        </p>
        <p className="text-xs mt-0.5 text-[rgb(var(--text-muted))]">
          {step.state === "active" ? (
            <ActiveDetail text={step.detail} reduce={reduce} />
          ) : step.detail}
        </p>
      </div>

      {/* State chip */}
      {step.state === "done" && (
        <motion.span
          initial={reduce ? false : { scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 300, damping: 20 }}
          className="shrink-0 text-[10px] px-2 py-0.5 rounded-full font-medium"
          style={{
            background: "rgb(var(--aura)/0.12)",
            color: "rgb(var(--aura))",
            border: "1px solid rgb(var(--aura)/0.25)"
          }}
        >
          {lang === "ar" ? "تم" : "Done"}
        </motion.span>
      )}
    </motion.div>
  );
}

function ActiveDetail({ text, reduce }: { text: string; reduce: boolean }) {
  const [dots, setDots] = useState(".");
  useEffect(() => {
    if (reduce) return;
    const iv = setInterval(() => setDots(d => d.length >= 3 ? "." : d + "."), 400);
    return () => clearInterval(iv);
  }, [reduce]);
  return <>{text}{dots}</>;
}

const THINKING_PHRASES_EN = [
  "Reviewing your career goals",
  "Analysing market conditions in UAE",
  "Comparing your skills to role requirements",
];

const THINKING_PHRASES_AR = [
  "مراجعة أهدافك المهنية",
  "تحليل ظروف السوق في الإمارات",
  "مقارنة مهاراتك بمتطلبات الدور",
];

export function ThinkingState({ lang }: { lang: "en" | "ar" }) {
  const reduce = useReducedMotion() ?? false;
  const [phraseIdx, setPhraseIdx] = useState(0);
  const phrases = lang === "ar" ? THINKING_PHRASES_AR : THINKING_PHRASES_EN;
  const steps = lang === "ar" ? TOOL_STEPS_AR : TOOL_STEPS_EN;

  useEffect(() => {
    if (reduce) return;
    const iv = setInterval(() => setPhraseIdx(i => (i + 1) % phrases.length), 2800);
    return () => clearInterval(iv);
  }, [reduce, phrases.length]);

  return (
    <div className="py-8 space-y-8">
      <SectionLabel text={lang === "ar" ? "حالة تفكير الذكاء الاصطناعي" : "AI Thinking State"} />

      {/* Two-column: orb + phrase / tool rail */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Left — thinking orb + phrase */}
        <div className="glass-panel rounded-[20px] p-6 flex flex-col gap-6">
          <div className="flex items-center gap-4">
            {/* Orb */}
            <div className="relative shrink-0">
              <motion.div
                animate={reduce ? {} : { scale: [1, 1.06, 1] }}
                transition={{ repeat: Infinity, duration: 2.4, ease: "easeInOut" }}
                className="w-12 h-12 rounded-full flex items-center justify-center font-bold text-base"
                style={{
                  background: "radial-gradient(circle at 38% 32%, rgb(var(--gold-hover)), rgb(var(--gold)))",
                  color: "var(--rico-on-primary)",
                  boxShadow: "0 0 24px rgb(var(--gold) / 0.32), inset 0 1px 0 rgb(var(--overlay) / 0.22)"
                }}
              >
                R
              </motion.div>
              {/* Pulse ring */}
              {!reduce && (
                <motion.div
                  animate={{ scale: [1, 1.7], opacity: [0.5, 0] }}
                  transition={{ repeat: Infinity, duration: 2, ease: "easeOut" }}
                  className="absolute inset-0 rounded-full pointer-events-none"
                  style={{ border: "1.5px solid rgb(var(--gold) / 0.4)" }}
                />
              )}
            </div>

            <div className="flex flex-col gap-1">
              <span className="text-xs text-[rgb(var(--text-tertiary))] uppercase tracking-wider font-mono">
                {lang === "ar" ? "يعالج" : "Processing"}
              </span>
              <AnimatePresence mode="wait">
                <motion.p
                  key={phraseIdx}
                  initial={reduce ? false : { opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduce ? {} : { opacity: 0, y: -6 }}
                  transition={{ duration: 0.28 }}
                  className="text-sm text-[rgb(var(--text-primary))] font-medium leading-snug"
                >
                  {phrases[phraseIdx]}
                </motion.p>
              </AnimatePresence>
            </div>
          </div>

          {/* Skeleton response preview */}
          <div className="space-y-2" aria-label={lang === "ar" ? "جارٍ تحميل معاينة الرد" : "Loading response preview"}>
            {[80, 60, 90, 45].map((w, i) => (
              <motion.div
                key={i}
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.1 }}
                className="skeleton-shimmer rounded h-3"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
        </div>

        {/* Right — tool activity rail */}
        <div className="glass-panel rounded-[20px] p-6">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs text-[rgb(var(--text-tertiary))] uppercase tracking-wider font-mono">
              {lang === "ar" ? "سجل النشاط — تجريبي" : "Activity Rail — Demo"}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full font-mono"
              style={{ background: "rgb(var(--gold)/0.10)", color: "rgb(var(--gold))", border: "1px solid rgb(var(--gold)/0.20)" }}>
              SIMULATED
            </span>
          </div>
          <div className="divide-y divide-[rgb(var(--overlay)/0.05)]">
            {steps.map((step, i) => (
              <ToolStep key={step.id} step={step} index={i} reduce={reduce} lang={lang} />
            ))}
          </div>
        </div>
      </div>

      {/* Depth card — 3D CSS transform */}
      <DepthCard lang={lang} reduce={reduce} />
    </div>
  );
}

function DepthCard({ lang, reduce }: { lang: "en" | "ar"; reduce: boolean }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ perspective: "900px" }}
    >
      <motion.div
        animate={hovered && !reduce ? { rotateX: -4, rotateY: 5, scale: 1.01 } : { rotateX: 0, rotateY: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 180, damping: 22 }}
        className="glass-panel rounded-[20px] p-6 cursor-default"
        style={{ transformStyle: "preserve-3d" }}
      >
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1">
            <p className="text-xs text-[rgb(var(--text-tertiary))] uppercase tracking-wider font-mono mb-1">
              {lang === "ar" ? "رسالة ريكو" : "Rico Message"}
            </p>
            <p className="text-sm text-[rgb(var(--text-primary))] leading-relaxed" dir={lang === "ar" ? "rtl" : "ltr"}>
              {lang === "ar"
                ? "لقد وجدت 4 وظائف تتوافق مع مستوى مهاراتك وأهدافك. سأعرضها عليك مع شرح لكل تطابق."
                : "I found 4 roles that align with your skills and goals. Let me walk you through each match with context."}
            </p>
          </div>
          <motion.div
            animate={hovered && !reduce ? { translateZ: 12 } : { translateZ: 0 }}
            transition={{ type: "spring", stiffness: 200, damping: 24 }}
            className="shrink-0 text-xs px-4 py-2 rounded-full font-medium"
            style={{
              background: "rgb(var(--gold)/0.15)",
              border: "1px solid rgb(var(--gold)/0.35)",
              color: "rgb(var(--gold))",
            }}
          >
            {lang === "ar" ? "عرض النتائج" : "View results"}
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}

function SectionLabel({ text }: { text: string }) {
  return (
    <p className="text-xs text-[rgb(var(--text-muted))] uppercase tracking-widest font-mono">
      {text}
    </p>
  );
}
