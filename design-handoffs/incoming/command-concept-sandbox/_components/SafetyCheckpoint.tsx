"use client";

/**
 * SANDBOX PROTOTYPE COMPONENT — SafetyCheckpoint
 * Demonstrates Rico's safety-gate UI before taking a high-impact action.
 * The action is DEMO only — no real application or backend call is made.
 */

import { useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";

type GateState = "pending" | "approved" | "rejected";

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

function GateIcon({ state }: { state: GateState }) {
  if (state === "approved") return (
    <motion.span
      key="approved"
      initial={{ scale: 0 }}
      animate={{ scale: 1 }}
      transition={{ type: "spring", stiffness: 320, damping: 20 }}
      style={{ color: "rgb(var(--success))", fontSize: 20 }}
    >✓</motion.span>
  );
  if (state === "rejected") return (
    <motion.span
      key="rejected"
      initial={{ scale: 0 }}
      animate={{ scale: 1 }}
      transition={{ type: "spring", stiffness: 320, damping: 20 }}
      style={{ color: "rgb(var(--text-muted))", fontSize: 20 }}
    >✕</motion.span>
  );
  return (
    <motion.span
      key="shield"
      animate={{ scale: [1, 1.08, 1] }}
      transition={{ repeat: Infinity, duration: 2.2, ease: "easeInOut" }}
      style={{ fontSize: 20 }}
    >
      ◈
    </motion.span>
  );
}

export function SafetyCheckpoint({ lang }: { lang: "en" | "ar" }) {
  const reduce = useReducedMotion() ?? false;
  const [gate, setGate] = useState<GateState>("pending");
  const risks = lang === "ar" ? RISKS_AR : RISKS_EN;
  const dir = lang === "ar" ? "rtl" : "ltr";

  return (
    <div className="py-8 space-y-6" dir={dir}>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <p className="text-xs text-[rgb(var(--text-muted))] uppercase tracking-widest font-mono">
          {lang === "ar" ? "نقطة التحقق الأمنية — تجريبي" : "Safety Checkpoint — Demo"}
        </p>
        <span className="text-[10px] px-2 py-0.5 rounded-full font-mono"
          style={{ background: "rgb(var(--gold)/0.10)", color: "rgb(var(--gold))", border: "1px solid rgb(var(--gold)/0.20)" }}>
          DEMO — no real action
        </span>
      </div>

      <div className="max-w-2xl mx-auto space-y-4">
        {/* Gate card */}
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
                background: gate === "approved"
                  ? "rgb(var(--success)/0.15)"
                  : gate === "rejected"
                  ? "rgb(var(--overlay)/0.08)"
                  : "rgb(var(--gold)/0.12)",
                border: `1px solid ${gate === "approved" ? "rgb(var(--success)/0.3)" : gate === "rejected" ? "rgb(var(--overlay)/0.12)" : "rgb(var(--gold)/0.3)"}`,
              }}
            >
              <GateIcon state={gate} />
            </div>
            <div>
              <p className="text-sm font-semibold text-[rgb(var(--text-primary))] leading-none">
                {gate === "approved"
                  ? (lang === "ar" ? "تمت الموافقة — سيتم تنفيذ الإجراء" : "Approved - Action will proceed")
                  : gate === "rejected"
                  ? (lang === "ar" ? "تم الرفض — لم يُتخذ أي إجراء" : "Declined - No action taken")
                  : (lang === "ar" ? "يلزم تأكيدك قبل المتابعة" : "Your confirmation required before proceeding")
                }
              </p>
              <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5">
                {gate === "pending" && (lang === "ar" ? "إجراء عالي التأثير" : "High-impact action")}
                {gate === "approved" && (lang === "ar" ? "تمت معالجة الطلب بنجاح" : "Request processed successfully")}
                {gate === "rejected" && (lang === "ar" ? "جلستك آمنة" : "Your session is safe")}
              </p>
            </div>
          </div>

          {/* Rico explainer */}
          <div className="px-5 py-4 flex gap-3 border-b border-[rgb(var(--overlay)/0.07)]">
            <div className="w-6 h-6 rounded-full flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5"
              style={{ background: "radial-gradient(circle, rgb(255 196 110), rgb(240 169 74))", color: "#0a0a0f" }}>
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

          {/* Buttons */}
          <AnimatePresence mode="wait">
            {gate === "pending" && (
              <motion.div
                key="buttons"
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={reduce ? {} : { opacity: 0 }}
                className="px-5 py-4 border-t border-[rgb(var(--overlay)/0.07)] flex gap-3 flex-wrap"
              >
                <button
                  onClick={() => setGate("approved")}
                  className="flex-1 text-sm px-5 py-2.5 rounded-full font-medium transition-all active:scale-[0.97]"
                  style={{
                    background: "rgb(var(--success)/0.15)",
                    border: "1px solid rgb(var(--success)/0.35)",
                    color: "rgb(var(--success))",
                  }}
                >
                  {lang === "ar" ? "نعم، وافق على الإرسال" : "Yes, approve submission"}
                </button>
                <button
                  onClick={() => setGate("rejected")}
                  className="flex-1 text-sm px-5 py-2.5 rounded-full font-medium transition-all active:scale-[0.97] text-[rgb(var(--text-tertiary))] border border-[rgb(var(--overlay)/0.12)] hover:border-[rgb(var(--overlay)/0.2)] hover:text-[rgb(var(--text-secondary))]"
                >
                  {lang === "ar" ? "لا، أوقف الإجراء" : "No, cancel"}
                </button>
              </motion.div>
            )}

            {gate !== "pending" && (
              <motion.div
                key="result"
                initial={reduce ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="px-5 py-4 border-t border-[rgb(var(--overlay)/0.07)]"
              >
                <p className="text-sm text-[rgb(var(--text-secondary))] leading-relaxed">
                  {gate === "approved"
                    ? (lang === "ar"
                      ? "تمت الموافقة. سأعلمك بالتقدم في صندوق الوارد ومتابعات التطبيق."
                      : "Approved. I will keep you updated on progress in your inbox and application tracker.")
                    : (lang === "ar"
                      ? "لا بأس. تم إلغاء الإجراء. بإمكانك الرجوع إليه في أي وقت من صفحة نتائج الوظائف."
                      : "No problem. Action cancelled. You can revisit this any time from your job results.")}
                </p>
                <button
                  onClick={() => setGate("pending")}
                  className="mt-3 text-xs text-[rgb(var(--text-muted))] underline underline-offset-2 hover:text-[rgb(var(--text-secondary))] transition-colors"
                >
                  {lang === "ar" ? "إعادة تشغيل العرض التجريبي" : "Reset demo"}
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </div>
  );
}
