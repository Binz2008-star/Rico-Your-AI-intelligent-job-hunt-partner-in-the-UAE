// Self-contained EN/AR strings for the owner-only subscriber admin surface.
// Kept local (not in the shared translations.ts) because this is an internal
// owner tool — this avoids bloating the app-wide translation bundle while still
// providing full English + Arabic/RTL coverage.

export type SubLang = "en" | "ar";

export interface SubStrings {
  navSubscribers: string;
  title: string;
  subtitle: string;
  ownerOnly: string;
  refresh: string;
  refreshing: string;
  lastRefresh: string;
  lastSynced: string;
  neverSynced: string;
  autoRefreshLive: string;
  autoRefreshPaused: string;
  loading: string;
  empty: string;
  failed: string;
  retry: string;
  partialUsage: string;
  stale: string;
  truncated: string;
  search: string;
  // summary
  totalUsers: string;
  freeUsers: string;
  active: string;
  pastDue: string;
  canceling: string;
  canceled: string;
  expired: string;
  paymentFailed: string;
  needsReconciliation: string;
  newThisMonth: string;
  cancellationsThisMonth: string;
  mrr: string;
  approx: string;
  // table headers
  colName: string;
  colEmail: string;
  colUserId: string;
  colPlan: string;
  colStatus: string;
  colPaddle: string;
  colStart: string;
  colRenewal: string;
  colCancelEffective: string;
  colAiUsage: string;
  colSavedUsage: string;
  colDocUsage: string;
  colLastActivity: string;
  colLastSync: string;
  colReconciliation: string;
  // filters
  filterAll: string;
  filterInactive7: string;
  filterInactive30: string;
  // plans
  planRicoMonthly: string;
  planFree: string;
  // status labels
  statusFree: string;
  statusActive: string;
  statusTrialing: string;
  statusCanceling: string;
  statusPastDue: string;
  statusPaymentFailed: string;
  statusCanceled: string;
  statusExpired: string;
  statusPaused: string;
  statusNeedsReconciliation: string;
  reconOk: string;
  reconNeedsReview: string;
  notAvailable: string;
  ofAllowance: string;
}

const en: SubStrings = {
  navSubscribers: "Subscribers",
  title: "Subscribers",
  subtitle: "Owner-only view of registered users and Rico Monthly billing state.",
  ownerOnly: "Owner only",
  refresh: "Refresh",
  refreshing: "Refreshing…",
  lastRefresh: "Last refresh",
  lastSynced: "Last billing sync",
  neverSynced: "No billing sync yet",
  autoRefreshLive: "Auto-refresh on",
  autoRefreshPaused: "Auto-refresh paused (tab hidden)",
  loading: "Loading subscribers…",
  empty: "No subscribers match this view.",
  failed: "Could not load subscribers. Showing the last known data if available.",
  retry: "Try again",
  partialUsage: "Usage figures are temporarily unavailable — billing state is current.",
  stale: "Data may be stale — last refresh failed.",
  truncated: "Showing the first accounts only (list truncated).",
  search: "Search by name or email",
  totalUsers: "Total registered users",
  freeUsers: "Free users",
  active: "Active",
  pastDue: "Past due",
  canceling: "Canceling",
  canceled: "Canceled",
  expired: "Expired",
  paymentFailed: "Payment failed",
  needsReconciliation: "Needs reconciliation",
  newThisMonth: "New this month",
  cancellationsThisMonth: "Cancellations this month",
  mrr: "Monthly recurring revenue",
  approx: "approx.",
  colName: "Name",
  colEmail: "Email",
  colUserId: "User ID",
  colPlan: "Plan",
  colStatus: "Status",
  colPaddle: "Paddle ref",
  colStart: "Started",
  colRenewal: "Next renewal",
  colCancelEffective: "Cancels on",
  colAiUsage: "AI (30d)",
  colSavedUsage: "Saved jobs",
  colDocUsage: "CV / docs",
  colLastActivity: "Last activity",
  colLastSync: "Last sync",
  colReconciliation: "Reconciliation",
  filterAll: "All",
  filterInactive7: "Inactive 7 days",
  filterInactive30: "Inactive 30 days",
  planRicoMonthly: "Rico Monthly",
  planFree: "Free",
  statusFree: "Free",
  statusActive: "Active",
  statusTrialing: "Trialing",
  statusCanceling: "Canceling",
  statusPastDue: "Past due",
  statusPaymentFailed: "Payment failed",
  statusCanceled: "Canceled",
  statusExpired: "Expired",
  statusPaused: "Paused",
  statusNeedsReconciliation: "Needs reconciliation",
  reconOk: "OK",
  reconNeedsReview: "Needs review",
  notAvailable: "—",
  ofAllowance: "of",
};

const ar: SubStrings = {
  navSubscribers: "المشتركون",
  title: "المشتركون",
  subtitle: "عرض خاص بالمالك للمستخدمين المسجّلين وحالة اشتراك ريكو الشهري.",
  ownerOnly: "للمالك فقط",
  refresh: "تحديث",
  refreshing: "جارٍ التحديث…",
  lastRefresh: "آخر تحديث",
  lastSynced: "آخر مزامنة فوترة",
  neverSynced: "لا توجد مزامنة فوترة بعد",
  autoRefreshLive: "التحديث التلقائي مُفعّل",
  autoRefreshPaused: "التحديث التلقائي متوقف (التبويب مخفي)",
  loading: "جارٍ تحميل المشتركين…",
  empty: "لا يوجد مشتركون مطابقون لهذا العرض.",
  failed: "تعذّر تحميل المشتركين. يتم عرض آخر بيانات معروفة إن وُجدت.",
  retry: "إعادة المحاولة",
  partialUsage: "أرقام الاستخدام غير متوفرة مؤقتًا — حالة الفوترة محدّثة.",
  stale: "قد تكون البيانات قديمة — فشل آخر تحديث.",
  truncated: "يتم عرض أوائل الحسابات فقط (القائمة مقتطعة).",
  search: "ابحث بالاسم أو البريد الإلكتروني",
  totalUsers: "إجمالي المستخدمين المسجّلين",
  freeUsers: "المستخدمون المجانيون",
  active: "نشط",
  pastDue: "متأخر السداد",
  canceling: "قيد الإلغاء",
  canceled: "ملغى",
  expired: "منتهي",
  paymentFailed: "فشل الدفع",
  needsReconciliation: "بحاجة إلى تسوية",
  newThisMonth: "جديد هذا الشهر",
  cancellationsThisMonth: "إلغاءات هذا الشهر",
  mrr: "الإيراد الشهري المتكرر",
  approx: "تقريبًا",
  colName: "الاسم",
  colEmail: "البريد الإلكتروني",
  colUserId: "معرّف المستخدم",
  colPlan: "الخطة",
  colStatus: "الحالة",
  colPaddle: "مرجع Paddle",
  colStart: "تاريخ البدء",
  colRenewal: "التجديد التالي",
  colCancelEffective: "يُلغى في",
  colAiUsage: "الذكاء الاصطناعي (30 يومًا)",
  colSavedUsage: "الوظائف المحفوظة",
  colDocUsage: "السيرة / المستندات",
  colLastActivity: "آخر نشاط",
  colLastSync: "آخر مزامنة",
  colReconciliation: "التسوية",
  filterAll: "الكل",
  filterInactive7: "غير نشط 7 أيام",
  filterInactive30: "غير نشط 30 يومًا",
  planRicoMonthly: "ريكو الشهري",
  planFree: "مجاني",
  statusFree: "مجاني",
  statusActive: "نشط",
  statusTrialing: "تجريبي",
  statusCanceling: "قيد الإلغاء",
  statusPastDue: "متأخر السداد",
  statusPaymentFailed: "فشل الدفع",
  statusCanceled: "ملغى",
  statusExpired: "منتهي",
  statusPaused: "متوقف مؤقتًا",
  statusNeedsReconciliation: "بحاجة إلى تسوية",
  reconOk: "سليم",
  reconNeedsReview: "بحاجة إلى مراجعة",
  notAvailable: "—",
  ofAllowance: "من",
};

export const SUBSCRIBERS_STRINGS: Record<SubLang, SubStrings> = { en, ar };

export function subscribersStrings(language: string): SubStrings {
  return language === "ar" ? ar : en;
}

// Machine status key -> localized label.
export function statusLabel(s: SubStrings, status: string): string {
  const map: Record<string, string> = {
    free: s.statusFree,
    active: s.statusActive,
    trialing: s.statusTrialing,
    canceling: s.statusCanceling,
    past_due: s.statusPastDue,
    payment_failed: s.statusPaymentFailed,
    canceled: s.statusCanceled,
    expired: s.statusExpired,
    paused: s.statusPaused,
    needs_reconciliation: s.statusNeedsReconciliation,
  };
  return map[status] ?? status;
}

export function planLabel(s: SubStrings, plan: string): string {
  return plan === "rico_monthly" ? s.planRicoMonthly : s.planFree;
}
