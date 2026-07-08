"use client";

/**
 * SANDBOX PROTOTYPE — /sandbox/command-concept
 *
 * Design prototype only. Not linked from production navigation.
 * No production routes, backend, auth, or billing touched.
 * All tool activity shown here is SIMULATED / DEMO data.
 * No AI provider names exposed.
 */

import { useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { ThinkingState } from "./_components/ThinkingState";
import { JobIntelCard } from "./_components/JobIntelCard";
import { SafetyCheckpoint } from "./_components/SafetyCheckpoint";
import { ChatThread } from "./_components/ChatThread";

const DEMO_LABEL = (
  <div className="fixed top-3 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
    <span className="bg-[rgb(var(--gold)/0.15)] border border-[rgb(var(--gold)/0.30)] text-[rgb(var(--gold))] text-[10px] font-mono uppercase tracking-widest px-3 py-1 rounded-full">
      Prototype — demo data only
    </span>
  </div>
);

type Scene = "idle" | "thinking" | "cards" | "safety" | "thread";

const SCENES: { key: Scene; label: string; labelAr: string }[] = [
  { key: "thinking", label: "AI Thinking State", labelAr: "حالة التفكير" },
  { key: "cards",   label: "Job Intelligence",  labelAr: "ذكاء الوظائف" },
  { key: "safety",  label: "Safety Checkpoint", labelAr: "نقطة الأمان" },
  { key: "thread",  label: "Chat Thread",       labelAr: "المحادثة" },
];

export default function CommandConceptSandbox() {
  const [scene, setScene] = useState<Scene>("thinking");
  const [lang, setLang] = useState<"en" | "ar">("en");
  const reduce = useReducedMotion();

  return (
    <div className="command-dark-lock min-h-[100dvh] bg-[rgb(var(--bg))] text-[rgb(var(--text-primary))] relative overflow-x-hidden">
      {DEMO_LABEL}

      {/* Ambient glow blobs — CSS only, reduced-motion safe */}
      <div aria-hidden className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full animate-pulse-gold opacity-40"
          style={{ background: "radial-gradient(circle, rgb(var(--gold) / 0.07) 0%, transparent 70%)", filter: "blur(80px)" }} />
        <div className="absolute -bottom-40 -right-40 w-[500px] h-[500px] rounded-full animate-pulse-magenta opacity-30"
          style={{ background: "radial-gradient(circle, rgb(var(--magenta) / 0.06) 0%, transparent 70%)", filter: "blur(100px)" }} />
      </div>

      {/* Nav bar */}
      <header className="sticky top-0 z-40 glass-island px-4 md:px-8 h-14 flex items-center justify-between max-w-[1400px] mx-auto w-full">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-full bg-[rgb(var(--gold))] flex items-center justify-center text-[11px] font-bold text-[var(--rico-on-primary)] select-none">R</div>
          <span className="text-sm font-semibold text-[rgb(var(--text-primary))] tracking-tight">
            {lang === "ar" ? "ريكو — مفهوم تصميمي" : "Rico Command — Concept"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setLang(l => l === "en" ? "ar" : "en")}
            className="text-xs px-3 py-1.5 rounded-full border border-[rgb(var(--overlay)/0.12)] text-[rgb(var(--text-secondary))] hover:text-[rgb(var(--text-primary))] hover:border-[rgb(var(--overlay)/0.22)] transition-colors"
            aria-label="Toggle language"
          >
            {lang === "en" ? "عربي" : "EN"}
          </button>
        </div>
      </header>

      {/* Scene picker */}
      <div className="sticky top-14 z-30 px-4 md:px-8 py-3 max-w-[1400px] mx-auto">
        <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1" dir={lang === "ar" ? "rtl" : "ltr"}>
          {SCENES.map(s => (
            <button
              key={s.key}
              onClick={() => setScene(s.key)}
              className={[
                "shrink-0 text-xs px-4 py-2 rounded-full border transition-all",
                scene === s.key
                  ? "bg-[rgb(var(--gold)/0.15)] border-[rgb(var(--gold)/0.35)] text-[rgb(var(--gold))] font-medium"
                  : "border-[rgb(var(--overlay)/0.10)] text-[rgb(var(--text-tertiary))] hover:text-[rgb(var(--text-secondary))] hover:border-[rgb(var(--overlay)/0.18)]"
              ].join(" ")}
            >
              {lang === "ar" ? s.labelAr : s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stage */}
      <main className="px-4 md:px-8 pb-24 max-w-[1400px] mx-auto w-full" dir={lang === "ar" ? "rtl" : "ltr"}>
        <AnimatePresence mode="wait">
          <motion.div
            key={scene}
            initial={reduce ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? {} : { opacity: 0, y: -8 }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          >
            {scene === "thinking" && <ThinkingState lang={lang} />}
            {scene === "cards"    && <JobIntelCard lang={lang} />}
            {scene === "safety"   && <SafetyCheckpoint lang={lang} />}
            {scene === "thread"   && <ChatThread lang={lang} />}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
