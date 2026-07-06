"use client";

/**
 * SANDBOX PROTOTYPE COMPONENT — JobIntelCard
 * Explainable animated job intelligence cards with SVG score ring,
 * match reason reveal, and 3D-CSS depth hover.
 * All data is DEMO only.
 */

import { useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";

interface DemoJob {
  id: string;
  title: string;
  titleAr: string;
  company: string;
  location: string;
  locationAr: string;
  score: number;
  tag: string;
  tagAr: string;
  tagColor: "aura" | "gold" | "magenta";
  reasonsEn: string[];
  reasonsAr: string[];
  concernsEn: string[];
  concernsAr: string[];
  salary: string;
}

const DEMO_JOBS: DemoJob[] = [
  {
    id: "j1",
    title: "Senior Product Manager",
    titleAr: "مدير منتج أول",
    company: "Noon",
    location: "Dubai, UAE",
    locationAr: "دبي، الإمارات",
    score: 91,
    tag: "Strong match",
    tagAr: "تطابق قوي",
    tagColor: "aura",
    reasonsEn: [
      "5+ years PM experience aligns exactly",
      "UAE e-commerce background is a strong signal",
      "Arabic fluency is a listed requirement",
    ],
    reasonsAr: [
      "5+ سنوات من خبرة إدارة المنتج تتوافق بدقة",
      "خلفية التجارة الإلكترونية في الإمارات إشارة قوية",
      "إتقان اللغة العربية من المتطلبات المدرجة",
    ],
    concernsEn: ["Role may require relocation to Riyadh for 3 months/year"],
    concernsAr: ["قد يتطلب الدور الانتقال إلى الرياض لمدة 3 أشهر سنوياً"],
    salary: "AED 32,000 – 42,000/mo",
  },
  {
    id: "j2",
    title: "Engineering Manager",
    titleAr: "مدير هندسي",
    company: "Careem",
    location: "Abu Dhabi, UAE",
    locationAr: "أبوظبي، الإمارات",
    score: 74,
    tag: "Good match",
    tagAr: "تطابق جيد",
    tagColor: "gold",
    reasonsEn: [
      "Team leadership experience matches",
      "Backend systems background is relevant",
    ],
    reasonsAr: [
      "خبرة قيادة الفريق تتوافق مع المتطلبات",
      "خلفية أنظمة الواجهة الخلفية ذات صلة",
    ],
    concernsEn: [
      "Role requires 8+ years; your profile shows 6",
      "Salary band slightly below market",
    ],
    concernsAr: [
      "يتطلب الدور 8+ سنوات؛ ملفك الشخصي يظهر 6",
      "نطاق الراتب أقل قليلاً من المعدل السوقي",
    ],
    salary: "AED 25,000 – 33,000/mo",
  },
  {
    id: "j3",
    title: "Head of Growth",
    titleAr: "رئيس قسم النمو",
    company: "Tabby",
    location: "Dubai, UAE",
    locationAr: "دبي، الإمارات",
    score: 58,
    tag: "Possible",
    tagAr: "محتمل",
    tagColor: "magenta",
    reasonsEn: ["Growth marketing experience is transferable"],
    reasonsAr: ["خبرة تسويق النمو قابلة للتحويل"],
    concernsEn: [
      "Role is fintech-focused; your background is e-commerce",
      "Asks for MENA market metrics you may not have",
    ],
    concernsAr: [
      "الدور يركز على التكنولوجيا المالية؛ خلفيتك تجارة إلكترونية",
      "يطلب مقاييس سوق الشرق الأوسط التي قد لا تمتلكها",
    ],
    salary: "AED 22,000 – 28,000/mo",
  },
];

const tagColorMap = {
  aura:    { bg: "rgb(var(--aura)/0.12)",    border: "rgb(var(--aura)/0.28)",    text: "rgb(var(--aura))"    },
  gold:    { bg: "rgb(var(--gold)/0.12)",    border: "rgb(var(--gold)/0.28)",    text: "rgb(var(--gold))"    },
  magenta: { bg: "rgb(var(--magenta)/0.12)", border: "rgb(var(--magenta)/0.28)", text: "rgb(var(--magenta))" },
};

const RING_R = 28;
const RING_CIRC = 2 * Math.PI * RING_R;

function ScoreRing({ score, color, reduce }: { score: number; color: string; reduce: boolean }) {
  const offset = RING_CIRC * (1 - score / 100);
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" aria-label={`Match score ${score}%`} role="img">
      <circle cx="36" cy="36" r={RING_R} fill="none" stroke="rgb(var(--overlay)/0.08)" strokeWidth="4" />
      <motion.circle
        cx="36" cy="36" r={RING_R}
        fill="none"
        stroke={color}
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={RING_CIRC}
        initial={{ strokeDashoffset: RING_CIRC }}
        animate={{ strokeDashoffset: reduce ? offset : offset }}
        transition={reduce ? { duration: 0 } : { duration: 1.1, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
        transform="rotate(-90 36 36)"
      />
      <text x="36" y="36" textAnchor="middle" dominantBaseline="central"
        fill={color} fontSize="14" fontWeight="700" fontFamily="var(--font-display, sans-serif)">
        {score}
      </text>
    </svg>
  );
}

function Card({ job, lang, reduce }: { job: DemoJob; lang: "en" | "ar"; reduce: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const [hovered, setHovered] = useState(false);
  const tag = tagColorMap[job.tagColor];
  const reasons = lang === "ar" ? job.reasonsAr : job.reasonsEn;
  const concerns = lang === "ar" ? job.concernsAr : job.concernsEn;

  return (
    <div style={{ perspective: "900px" }}>
      <motion.div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        animate={hovered && !reduce ? { rotateX: -2, rotateY: 3, scale: 1.01 } : { rotateX: 0, rotateY: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 200, damping: 24 }}
        className="glass-panel rounded-[20px] overflow-hidden"
        style={{ transformStyle: "preserve-3d" }}
      >
        {/* Header */}
        <div className="p-5 flex items-start gap-4">
          <ScoreRing
            score={job.score}
            color={tag.text}
            reduce={reduce}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <div>
                <p className="font-semibold text-[rgb(var(--text-primary))] leading-snug">
                  {lang === "ar" ? job.titleAr : job.title}
                </p>
                <p className="text-sm text-[rgb(var(--text-secondary))] mt-0.5">
                  {job.company} · {lang === "ar" ? job.locationAr : job.location}
                </p>
              </div>
              <span className="shrink-0 text-[11px] px-2.5 py-1 rounded-full font-medium"
                style={{ background: tag.bg, border: `1px solid ${tag.border}`, color: tag.text }}>
                {lang === "ar" ? job.tagAr : job.tag}
              </span>
            </div>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-2 font-mono">{job.salary}</p>
          </div>
        </div>

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded(e => !e)}
          className="w-full px-5 py-3 flex items-center justify-between border-t border-[rgb(var(--overlay)/0.07)] text-xs text-[rgb(var(--text-tertiary))] hover:text-[rgb(var(--text-secondary))] transition-colors"
          aria-expanded={expanded}
        >
          <span>{lang === "ar" ? "لماذا هذا التطابق؟" : "Why this match?"}</span>
          <motion.span
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            ↓
          </motion.span>
        </button>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={reduce ? false : { height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={reduce ? {} : { height: 0, opacity: 0 }}
              transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
              className="overflow-hidden"
            >
              <div className="px-5 pb-5 pt-1 space-y-4">
                {/* Reasons */}
                <div>
                  <p className="text-[10px] uppercase tracking-widest font-mono text-[rgb(var(--aura)/0.7)] mb-2">
                    {lang === "ar" ? "نقاط التطابق" : "Match signals"}
                  </p>
                  <ul className="space-y-1.5">
                    {reasons.map((r, i) => (
                      <motion.li
                        key={i}
                        initial={reduce ? false : { opacity: 0, x: lang === "ar" ? 8 : -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.06, duration: 0.24 }}
                        className="flex items-start gap-2 text-sm text-[rgb(var(--text-secondary))]"
                      >
                        <span style={{ color: "rgb(var(--aura))", marginTop: 2, flexShrink: 0 }}>✓</span>
                        {r}
                      </motion.li>
                    ))}
                  </ul>
                </div>

                {/* Concerns */}
                {concerns.length > 0 && (
                  <div>
                    <p className="text-[10px] uppercase tracking-widest font-mono text-[rgb(var(--gold)/0.7)] mb-2">
                      {lang === "ar" ? "نقاط يجب أخذها بعين الاعتبار" : "Worth noting"}
                    </p>
                    <ul className="space-y-1.5">
                      {concerns.map((c, i) => (
                        <motion.li
                          key={i}
                          initial={reduce ? false : { opacity: 0, x: lang === "ar" ? 8 : -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.15 + i * 0.06, duration: 0.24 }}
                          className="flex items-start gap-2 text-sm text-[rgb(var(--text-secondary))]"
                        >
                          <span style={{ color: "rgb(var(--gold))", marginTop: 2, flexShrink: 0 }}>!</span>
                          {c}
                        </motion.li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* CTA */}
                <div className="flex gap-2 pt-1 flex-wrap">
                  <button
                    className="text-xs px-4 py-2 rounded-full font-medium transition-all active:scale-[0.97]"
                    style={{
                      background: "rgb(var(--gold)/0.15)",
                      border: "1px solid rgb(var(--gold)/0.35)",
                      color: "rgb(var(--gold))",
                    }}
                    onClick={() => alert("Demo: apply action")}
                  >
                    {lang === "ar" ? "تقدم الآن" : "Apply now"}
                  </button>
                  <button
                    className="text-xs px-4 py-2 rounded-full font-medium transition-all active:scale-[0.97] text-[rgb(var(--text-tertiary))] border border-[rgb(var(--overlay)/0.10)] hover:border-[rgb(var(--overlay)/0.18)] hover:text-[rgb(var(--text-secondary))]"
                    onClick={() => alert("Demo: save action")}
                  >
                    {lang === "ar" ? "احفظ لاحقاً" : "Save for later"}
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

export function JobIntelCard({ lang }: { lang: "en" | "ar" }) {
  const reduce = useReducedMotion() ?? false;

  return (
    <div className="py-8 space-y-6" dir={lang === "ar" ? "rtl" : "ltr"}>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <p className="text-xs text-[rgb(var(--text-muted))] uppercase tracking-widest font-mono">
          {lang === "ar" ? "ذكاء الوظائف — تجريبي" : "Job Intelligence — Demo data"}
        </p>
        <span className="text-[10px] px-2 py-0.5 rounded-full font-mono"
          style={{ background: "rgb(var(--gold)/0.10)", color: "rgb(var(--gold))", border: "1px solid rgb(var(--gold)/0.20)" }}>
          SIMULATED
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {DEMO_JOBS.map((job, i) => (
          <motion.div
            key={job.id}
            initial={reduce ? false : { opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.36, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
          >
            <Card job={job} lang={lang} reduce={reduce} />
          </motion.div>
        ))}
      </div>

      {/* Rico summary line */}
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.3 }}
        className="glass-island rounded-[16px] p-4 flex items-start gap-3"
      >
        <div className="w-7 h-7 rounded-full flex items-center justify-center font-bold text-[11px] shrink-0"
          style={{ background: "radial-gradient(circle, rgb(255 196 110), rgb(240 169 74))", color: "#0a0a0f" }}>
          R
        </div>
        <p className="text-sm text-[rgb(var(--text-secondary))] leading-relaxed" dir={lang === "ar" ? "rtl" : "ltr"}>
          {lang === "ar"
            ? "هذه الوظائف الثلاث هي الأكثر توافقاً مع ملفك الشخصي الآن. استناداً إلى نمط طلباتك، أنصحك بالبدء بالوظيفة الأولى. هل تريد أن أساعدك في صياغة رسالة التقديم؟"
            : "These 3 roles are your strongest matches right now. Based on your application pattern, I recommend starting with the first one. Want me to help draft your application message?"}
        </p>
      </motion.div>
    </div>
  );
}
