"use client";

/**
 * SANDBOX PROTOTYPE COMPONENT — ChatThread
 * Cinematic chat thread with:
 * - Scroll-reveal message entry (whileInView)
 * - Animated thinking row (Rico is reading / preparing)
 * - Bilingual EN/AR message pairs (dir="rtl" for Arabic)
 * - Inline activity rail chip per assistant message
 * - Mobile-safe: no animation blocks input area
 *
 * ALL content is DEMO/SIMULATED.
 */

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";

type Role = "user" | "rico" | "system";

interface Message {
  id: string;
  role: Role;
  textEn: string;
  textAr: string;
  activityEn?: string;
  activityAr?: string;
  delay?: number;
}

const THREAD: Message[] = [
  {
    id: "m1",
    role: "user",
    textEn: "What's the best product manager role for me right now in the UAE?",
    textAr: "ما أفضل دور لمدير منتج مناسب لي الآن في الإمارات؟",
    delay: 0,
  },
  {
    id: "m2",
    role: "rico",
    textEn: "Let me check your profile, recent applications, and today's market. I'll also look at salary benchmarks for UAE PM roles at your level.",
    textAr: "دعني أطلع على ملفك الشخصي وطلباتك الأخيرة وسوق اليوم. سأتحقق أيضاً من معايير الرواتب لأدوار مدير المنتج في الإمارات بمستواك.",
    activityEn: "Read profile + market scan",
    activityAr: "قراءة الملف + فحص السوق",
    delay: 0.15,
  },
  {
    id: "m3",
    role: "system",
    textEn: "Rico completed profile read, job market scan, and salary benchmark in 1.2s",
    textAr: "أتم ريكو قراءة الملف وفحص سوق العمل ومعيار الراتب في 1.2 ثانية",
    delay: 0.3,
  },
  {
    id: "m4",
    role: "rico",
    textEn: "Found 4 strong matches. Your top pick is the Senior PM role at Noon — 91% match based on your e-commerce background and Arabic fluency. Salary range aligns with your target. Want me to walk through the full match?",
    textAr: "وجدت 4 تطابقات قوية. الخيار الأول هو دور مدير المنتج الأول في نون — تطابق 91% بناءً على خلفيتك في التجارة الإلكترونية وإجادتك للغة العربية. نطاق الراتب يتوافق مع هدفك. هل تريد أن أشرح التطابق الكامل؟",
    activityEn: "Score analysis complete",
    activityAr: "اكتمل تحليل النتيجة",
    delay: 0.45,
  },
  {
    id: "m5",
    role: "user",
    textEn: "Yes, and can you also check if I've applied to Noon before?",
    textAr: "نعم، هل يمكنك أيضاً التحقق مما إذا كنت قد تقدمت لنون من قبل؟",
    delay: 0.6,
  },
  {
    id: "m6",
    role: "rico",
    textEn: "Checked your application history — no prior applications to Noon found. Your last application in this category was to Careem in March 2025, which reached the final interview stage. This Noon role has a different team and a new budget cycle. Want me to prepare a targeted application now?",
    textAr: "راجعت تاريخ طلباتك — لا توجد طلبات سابقة لنون. آخر طلب في هذه الفئة كان لـ كريم في مارس 2025، وقد وصل إلى مرحلة المقابلة النهائية. هذا الدور في نون لديه فريق مختلف ودورة ميزانية جديدة. هل تريد مني إعداد طلب مخصص الآن؟",
    activityEn: "Application history checked",
    activityAr: "تم التحقق من تاريخ الطلبات",
    delay: 0.75,
  },
];

function ActivityChip({ text, reduce }: { text: string; reduce: boolean }) {
  return (
    <motion.span
      initial={reduce ? false : { opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.25, duration: 0.22 }}
      className="inline-flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-full font-mono"
      style={{
        background: "rgb(var(--aura)/0.10)",
        border: "1px solid rgb(var(--aura)/0.22)",
        color: "rgb(var(--aura)/0.8)",
      }}
    >
      <span style={{ fontSize: 8 }}>◉</span>
      {text}
    </motion.span>
  );
}

function MessageRow({ msg, lang, reduce }: { msg: Message; role?: Role; lang: "en" | "ar"; reduce: boolean }) {
  const isUser = msg.role === "user";
  const isSystem = msg.role === "system";
  const text = lang === "ar" ? msg.textAr : msg.textEn;
  const activity = lang === "ar" ? msg.activityAr : msg.activityEn;
  const dir = lang === "ar" ? "rtl" : "ltr";

  if (isSystem) {
    return (
      <motion.div
        initial={reduce ? false : { opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, amount: 0.5 }}
        transition={{ duration: 0.3, delay: msg.delay }}
        className="flex justify-center"
        dir={dir}
      >
        <span className="text-[10px] text-[rgb(var(--text-disabled))] font-mono px-3 py-1 rounded-full border border-[rgb(var(--overlay)/0.06)]">
          {text}
        </span>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 12, x: isUser ? 8 : -8 }}
      whileInView={{ opacity: 1, y: 0, x: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.32, delay: msg.delay, ease: [0.16, 1, 0.3, 1] }}
      className={["flex gap-3", isUser ? "flex-row-reverse" : "flex-row"].join(" ")}
      dir={dir}
    >
      {/* Avatar */}
      {!isUser && (
        <div className="w-7 h-7 rounded-full flex items-center justify-center font-bold text-[10px] shrink-0 mt-1"
          style={{ background: "radial-gradient(circle, rgb(var(--gold-hover)), rgb(var(--gold)))", color: "var(--rico-on-primary)" }}>
          R
        </div>
      )}

      {/* Bubble + activity chip */}
      <div className={["flex flex-col gap-1.5 max-w-[75%] md:max-w-[60%]", isUser ? "items-end" : "items-start"].join(" ")}>
        {activity && (
          <ActivityChip text={activity} reduce={reduce} />
        )}
        <div
          className="px-4 py-3 rounded-[16px] text-sm leading-relaxed"
          style={isUser ? {
            background: "rgb(var(--overlay)/0.07)",
            border: "1px solid rgb(var(--overlay)/0.12)",
            color: "rgb(var(--text-primary))",
          } : {
            background: "rgb(var(--surface-elevated))",
            border: "1px solid rgb(var(--overlay)/0.09)",
            color: "rgb(var(--text-primary))",
            boxShadow: "0 4px 16px rgb(var(--shadow-color)/0.16)",
          }}
          dir={dir}
        >
          {text}
        </div>
      </div>
    </motion.div>
  );
}

function ThinkingRow({ lang, reduce }: { lang: "en" | "ar"; reduce: boolean }) {
  const [dots, setDots] = useState(1);
  useEffect(() => {
    if (reduce) return;
    const iv = setInterval(() => setDots(d => d >= 3 ? 1 : d + 1), 380);
    return () => clearInterval(iv);
  }, [reduce]);

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduce ? {} : { opacity: 0 }}
      transition={{ duration: 0.24 }}
      className="flex gap-3 items-center"
      dir={lang === "ar" ? "rtl" : "ltr"}
    >
      <motion.div
        animate={reduce ? {} : { scale: [1, 1.06, 1] }}
        transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
        className="w-7 h-7 rounded-full flex items-center justify-center font-bold text-[10px] shrink-0"
        style={{ background: "radial-gradient(circle, rgb(var(--gold-hover)), rgb(var(--gold)))", color: "var(--rico-on-primary)" }}
      >
        R
      </motion.div>
      <div className="px-4 py-3 rounded-[16px] text-sm"
        style={{
          background: "rgb(var(--surface-elevated))",
          border: "1px solid rgb(var(--overlay)/0.09)",
          color: "rgb(var(--text-tertiary))",
        }}>
        {lang === "ar" ? "يفكر" : "Thinking"}
        {Array.from({ length: dots }).map((_, i) => (
          <span key={i} style={{ opacity: 0.6 }}>.</span>
        ))}
      </div>
    </motion.div>
  );
}

function InputBar({ lang }: { lang: "en" | "ar" }) {
  const dir = lang === "ar" ? "rtl" : "ltr";
  return (
    <div className="glass-island rounded-[16px] p-3 flex items-center gap-3" dir={dir}>
      <input
        type="text"
        readOnly
        placeholder={lang === "ar" ? "اكتب رسالتك… (عرض تجريبي)" : "Type your message… (demo)"}
        className="flex-1 bg-transparent text-sm text-[rgb(var(--text-secondary))] placeholder-[rgb(var(--text-disabled))] outline-none"
        dir={dir}
        aria-label={lang === "ar" ? "مدخل الرسالة — تجريبي" : "Message input — demo"}
      />
      <button
        className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm transition-all active:scale-95"
        style={{
          background: "rgb(var(--gold)/0.15)",
          border: "1px solid rgb(var(--gold)/0.35)",
          color: "rgb(var(--gold))",
        }}
        aria-label={lang === "ar" ? "إرسال — تجريبي" : "Send — demo"}
        onClick={() => {}}
      >
        ↑
      </button>
    </div>
  );
}

export function ChatThread({ lang }: { lang: "en" | "ar" }) {
  const reduce = useReducedMotion() ?? false;
  const [showThinking, setShowThinking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const handleSimulate = () => {
    setShowThinking(true);
    setTimeout(() => setShowThinking(false), 2800);
  };

  useEffect(() => {
    if (showThinking) {
      bottomRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
    }
  }, [showThinking, reduce]);

  return (
    <div className="py-8 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <p className="text-xs text-[rgb(var(--text-muted))] uppercase tracking-widest font-mono">
          {lang === "ar" ? "المحادثة — تجريبي" : "Chat Thread — Demo"}
        </p>
        <div className="flex items-center gap-2">
          <span className="text-[10px] px-2 py-0.5 rounded-full font-mono"
            style={{ background: "rgb(var(--gold)/0.10)", color: "rgb(var(--gold))", border: "1px solid rgb(var(--gold)/0.20)" }}>
            SIMULATED
          </span>
          <button
            onClick={handleSimulate}
            className="text-[10px] px-3 py-1.5 rounded-full border transition-colors text-[rgb(var(--text-tertiary))] border-[rgb(var(--overlay)/0.12)] hover:text-[rgb(var(--text-secondary))] hover:border-[rgb(var(--overlay)/0.20)]"
          >
            {lang === "ar" ? "محاكاة التفكير" : "Simulate thinking"}
          </button>
        </div>
      </div>

      {/* Thread viewport */}
      <div className="glass-panel rounded-[20px] overflow-hidden">
        {/* Thread scroll area */}
        <div className="p-5 space-y-5 max-h-[520px] overflow-y-auto no-scrollbar">
          {THREAD.map(msg => (
            <MessageRow key={msg.id} msg={msg} lang={lang} reduce={reduce} />
          ))}

          <AnimatePresence>
            {showThinking && (
              <ThinkingRow key="thinking" lang={lang} reduce={reduce} />
            )}
          </AnimatePresence>

          <div ref={bottomRef} />
        </div>

        {/* Input bar — never animated, always accessible */}
        <div className="border-t border-[rgb(var(--overlay)/0.07)] p-3">
          <InputBar lang={lang} />
        </div>
      </div>

      {/* Context note */}
      <p className="text-xs text-[rgb(var(--text-disabled))] text-center">
        {lang === "ar"
          ? "هذا عرض تجريبي للتصميم فقط. لا يتم إجراء أي استدعاءات حقيقية للذكاء الاصطناعي."
          : "Design prototype only. No real AI calls are made in this view."}
      </p>
    </div>
  );
}
