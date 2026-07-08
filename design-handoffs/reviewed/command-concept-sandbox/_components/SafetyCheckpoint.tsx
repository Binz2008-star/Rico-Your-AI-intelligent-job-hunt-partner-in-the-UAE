"use client";

/**
 * SANDBOX PROTOTYPE COMPONENT — SafetyCheckpoint
 *
 * DESIGN REFERENCE ONLY. This surface shows the LAYOUT of Rico's high-impact
 * action safety gate. It intentionally performs NO approval and persists NO
 * state:
 *   - The Approve / Cancel buttons are non-functional (disabled).
 *   - There is no frontend approval logic and no local state pretending an
 *     action was taken or saved.
 *
 * In production, a real high-impact action MUST route through:
 *   Intent -> Safety Policy -> Agent Runtime -> Persistence -> Confirmation
 * (see rico_safety.py, RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS,
 *  agent_runtime.handle_action, POST /api/v1/actions/{action}).
 */

import { motion, useReducedMotion } from "framer-motion";

interface ActionSummaryItem {
  labelEn: string;
  labelAr: string;
  value: string;
  valueAr?: string;
  highlight?: boolean;
}

const ACTION_ITEMS: ActionSummaryItem[] = [
  { labelEn: "Action",   labelAr: "الإجراء",     value: "Submit application",     valueAr: "إرسال طلب التوظيف", highlight: true },
  { labelEn: "Role",     labelAr: "الوظيفة",     value: "Senior Product Manager" },
  { labelEn: "Company",  labelAr: "الشركة",       value: "Noon" },
  { labelEn: "Location", labelAr: "الموقع",       value: "Dubai, UAE",             valueAr: "دبي، الإمارات" },
  { labelEn: "Match",    labelAr: "نسبة التطابق", value: "91%",                    highlight: true },
  { labelEn: "Source",   labelAr: "المصدر",       value: "LinkedIn Jobs" },
];

const RISKS_EN = [
  "This will submit your CV to a third-party job board.",
  "The company will receive your contact information.",
  "You cannot un-submit once sent.",
];

const RISKS_AR = [
  "سيتم إرسال سيرتك الذاتية إلى لوحة وظائف خارجية.",
  "ستتلقى الشركة معلومات الاتصال الخاصة بك.",
  "لا يمكنك التراجع عن الإرسال بعد إتمامه.",
];

const EXPLAINER_EN =
  "Before I take this action on your behalf, I need your explicit approval. This is a real-world action that cannot be undone automatically.";

const EXPLAINER_AR =
  "قبل أن أتخذ هذا الإجراء نيابةً عنك، أحتاج إلى موافقتك الصريحة. هذا إجراء في العالم الحقيقي ولا يمكن التراجع عنه تلقائياً.";

// The production routing contract this surface must be wired to before it can
// take any real action. Rendered as a reference below the gate card.
const ROUTING_STEPS_EN = ["Intent", "Safety Policy", "Agent Runtime", "Persistence", "Confirmation"];
const ROUTING_STEPS_AR = ["النية", "سياسة الأمان", "منفّذ الوكيل", "الحفظ", "التأكيد"];

function GateIcon({ reduce }: { reduce: boolean }) {
  return (
    <motion.span
      animate={reduce ? {} : { scale: [1, 1.08, 1] }}
      transition={{ repeat: Infinity, duration: 2.2, ease: "easeInOut" }}
      style={{ fontSize: 20 }}
    >
      ◈
    </motion.span>
  );
}

export function SafetyCheckpoint({ lang }: { lang: "en" | "ar" }) {
  const reduce = useReducedMotion() ?? false;
  const risks = lang === "ar" ? RISKS_AR : RISKS_EN;
  const routing = lang === "ar" ? ROUTING_STEPS_AR : ROUTING_STEPS_EN;
  const dir = lang === "ar" ? "rtl" : "ltr";

  return (
    <div className="py-8 space-y-6" dir={dir}>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <p className="text-xs text-[rgb(var(--text-muted))] uppercase tracking-widest font-mono">
          {lang === "ar" ? "نقطة التحقق الأمنية — مرجع تصميمي" : "Safety Checkpoint — Design reference"}
        </p>
        <span className="text-[10px] px-2 py-0.5 rounded-full font-mono"
          style={{ background: "rgb(var(--gold)/0.10)", color: "rgb(var(--gold))", border: "1px solid rgb(var(--gold)/0.20)" }}>
          {lang === "ar" ? "مرجع — بلا إجراء" : "REFERENCE — no action"}
        </span>
      </div>

      <div className="max-w-2xl mx-auto space-y-4">
        {/* Gate card — rendered at rest (pending). No state machine. */}
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
          className="glass-panel rounded-[20px] overflow-hidden"
        >
          {/* Top bar */}
          <div className="flex items-center gap-3 px-5 py-4 border-b border-[rgb(var(--overlay)/0.07)]">
            <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
              style={{
                background: "rgb(var(--gold)/0.12)",
                border: "1px solid rgb(var(--gold)/0.3)",
              }}
            >
              <GateIcon reduce={reduce} />
            </div>
            <div>
              <p className="text-sm font-semibold text-[rgb(var(--text-primary))] leading-none">
                {lang === "ar" ? "يلزم تأكيدك قبل المتابعة" : "Your confirmation required before proceeding"}
              </p>
              <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5">
                {lang === "ar" ? "إجراء عالي التأثير" : "High-impact action"}
              </p>
            </div>
          </div>

          {/* Rico explainer */}
          <div className="px-5 py-4 flex gap-3 border-b border-[rgb(var(--overlay)/0.07)]">
            <div className="w-6 h-6 rounded-full flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5"
              style={{ background: "radial-gradient(circle, rgb(var(--gold-hover)), rgb(var(--gold)))", color: "var(--rico-on-primary)" }}>
              R
            </div>
            <p className="text-sm text-[rgb(var(--text-secondary))] leading-relaxed">
              {lang === "ar" ? EXPLAINER_AR : EXPLAINER_EN}
            </p>
          </div>

          {/* Action summary table */}
          <div className="px-5 py-4 space-y-2.5">
            {ACTION_ITEMS.map((item, i) => (
              <motion.div
                key={i}
                initial={reduce ? false : { opacity: 0, x: lang === "ar" ? 8 : -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.05 + i * 0.05, duration: 0.22 }}
                className="flex items-center justify-between gap-4 text-sm"
              >
                <span className="text-[rgb(var(--text-tertiary))] shrink-0 min-w-[80px]">
                  {lang === "ar" ? item.labelAr : item.labelEn}
                </span>
                <span className={[
                  "font-medium text-right",
                  item.highlight ? "text-[rgb(var(--gold))]" : "text-[rgb(var(--text-primary))]"
                ].join(" ")}>
                  {lang === "ar" && item.valueAr ? item.valueAr : item.value}
                </span>
              </motion.div>
            ))}
          </div>

          {/* Risks */}
          <div className="px-5 py-4 border-t border-[rgb(var(--overlay)/0.07)] space-y-2">
            <p className="text-[10px] uppercase tracking-widest font-mono text-[rgb(var(--gold)/0.7)]">
              {lang === "ar" ? "يجب أن تعلم" : "What this means"}
            </p>
            <ul className="space-y-1.5">
              {risks.map((r, i) => (
                <li key={i} className="text-xs text-[rgb(var(--text-muted))] flex items-start gap-2">
                  <span className="shrink-0 mt-0.5" style={{ color: "rgb(var(--gold)/0.5)" }}>!</span>
                  {r}
                </li>
              ))}
            </ul>
          </div>

          {/* Buttons — NON-FUNCTIONAL design reference. No approval logic, no
              state change, no persistence. Real wiring is backend-owned. */}
          <div className="px-5 py-4 border-t border-[rgb(var(--overlay)/0.07)] flex gap-3 flex-wrap">
            <button
              type="button"
              disabled
              aria-disabled="true"
              title={lang === "ar" ? "غير فعّال — مرجع تصميمي" : "Non-functional — design reference"}
              className="flex-1 text-sm px-5 py-2.5 rounded-full font-medium cursor-not-allowed opacity-70"
              style={{
                background: "rgb(var(--success)/0.15)",
                border: "1px solid rgb(var(--success)/0.35)",
                color: "rgb(var(--success))",
              }}
            >
              {lang === "ar" ? "نعم، وافق على الإرسال" : "Yes, approve submission"}
            </button>
            <button
              type="button"
              disabled
              aria-disabled="true"
              title={lang === "ar" ? "غير فعّال — مرجع تصميمي" : "Non-functional — design reference"}
              className="flex-1 text-sm px-5 py-2.5 rounded-full font-medium cursor-not-allowed opacity-70 text-[rgb(var(--text-tertiary))] border border-[rgb(var(--overlay)/0.12)]"
            >
              {lang === "ar" ? "لا، أوقف الإجراء" : "No, cancel"}
            </button>
          </div>
        </motion.div>

        {/* Required production routing — makes the adaptation contract explicit. */}
        <div className="glass-island rounded-[16px] p-4 space-y-3">
          <p className="text-[10px] uppercase tracking-widest font-mono text-[rgb(var(--aura)/0.7)]">
            {lang === "ar" ? "مسار الإنتاج المطلوب" : "Required production routing"}
          </p>
          <div className="flex flex-wrap items-center gap-2" dir={dir}>
            {routing.map((step, i) => (
              <span key={step} className="flex items-center gap-2">
                <span className="text-xs px-3 py-1 rounded-full font-mono"
                  style={{
                    background: "rgb(var(--overlay)/0.06)",
                    border: "1px solid rgb(var(--overlay)/0.12)",
                    color: "rgb(var(--text-secondary))",
                  }}>
                  {step}
                </span>
                {i < routing.length - 1 && (
                  <span className="text-[rgb(var(--text-muted))]" aria-hidden>
                    {dir === "rtl" ? "←" : "→"}
                  </span>
                )}
              </span>
            ))}
          </div>
          <p className="text-xs text-[rgb(var(--text-muted))] leading-relaxed">
            {lang === "ar"
              ? "مرجع تصميمي فقط. لا تتم أي موافقة على الواجهة الأمامية ولا يُحفظ أي شيء. في الإنتاج، يجب أن يمر كل إجراء عبر المسار أعلاه."
              : "Design reference only. No approval happens in the frontend and nothing is persisted. In production, every action must flow through the pipeline above."}
          </p>
        </div>
      </div>
    </div>
  );
}
