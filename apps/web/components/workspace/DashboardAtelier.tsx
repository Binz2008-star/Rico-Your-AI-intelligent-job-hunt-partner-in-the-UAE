"use client";

/**
 * DashboardAtelier — the /dashboard Overview content, evolved toward the
 * frozen Command Workspace v4 reference (DEC-20260719-002, PR-V4-1):
 * goal panel + milestone pills + suggested next actions.
 *
 * Data is REAL, not sample: everything renders from the existing
 * GET /api/v1/mission/current (MissionState). The backend's `goal` /
 * `next_recommendation` / `blocking_reason` strings are English-only, so
 * bilingual presentation derives client-side from the STRUCTURED fields
 * (`target_roles`, `target_locations`) and the stable `missing_factors`
 * tokens (cv_uploaded / roles_set / locations_set / pipeline_active) —
 * same server truth, localized presentation. The reference's activity
 * timeline stays intentionally OMITTED (no production data source — per
 * DEC-20260710-002 no fake live data). Loading, error (with retry), and
 * empty-mission states are explicit; a failed load never renders zeroed
 * panels as if they were data.
 *
 * Visual system: shared atelier-kit tokens + Mono primitive; theme colors
 * come from WorkspaceShell via useWorkspaceTheme() so light/dark stays
 * consistent with the shell.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { Mono } from "@/components/atelier-kit/primitives";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { getMission, type MissionState } from "@/lib/api";

const SERIF = ATELIER_FONT.serif;

type Lang = "en" | "ar";

/* ── Mission factor tokens (server contract, src/services/mission_service.py) ── */

const FACTOR_TOKENS = [
    "cv_uploaded",
    "roles_set",
    "locations_set",
    "pipeline_active",
] as const;
type FactorToken = (typeof FACTOR_TOKENS)[number];

/* ── Suggested next actions (pure derivation, unit-tested) ────────────────── */

export type NextActionKey =
    | "upload_cv"
    | "set_goals"
    | "search_jobs"
    | "review_applications"
    | "keep_going"
    | "review_profile";

export const NEXT_ACTION_HREF: Record<NextActionKey, string> = {
    upload_cv: "/upload",
    set_goals: "/profile?section=goals",
    search_jobs: "/command",
    review_applications: "/applications",
    keep_going: "/command",
    review_profile: "/profile",
};

/**
 * Derive the max-3 "Suggested next" actions from real mission state only.
 * Priority mirrors the server's own missing-factor order; entries are
 * deduped by destination and capped at 3; the list is never empty.
 */
export function deriveNextActions(mission: MissionState | null): NextActionKey[] {
    const missing = new Set(mission?.missing_factors ?? FACTOR_TOKENS);
    const candidates: Array<{ key: NextActionKey; when: boolean }> = [
        { key: "upload_cv", when: missing.has("cv_uploaded") },
        { key: "set_goals", when: missing.has("roles_set") || missing.has("locations_set") },
        { key: "search_jobs", when: missing.has("pipeline_active") },
        { key: "review_applications", when: (mission?.applications_sent ?? 0) > 0 },
        { key: "keep_going", when: true },
        { key: "review_profile", when: true },
    ];
    const picked: NextActionKey[] = [];
    const seenHrefs = new Set<string>();
    for (const c of candidates) {
        if (picked.length >= 3) break;
        if (!c.when) continue;
        const href = NEXT_ACTION_HREF[c.key];
        if (seenHrefs.has(href)) continue;
        seenHrefs.add(href);
        picked.push(c.key);
    }
    return picked;
}

/* ── Bilingual copy (static UI copy only — never fabricated data) ─────────── */

const T: Record<Lang, {
    eyebrow: string; title: string; intro: string;
    goalEyebrow: string; goalSubtitle: string; goalEdit: string; progressAria: string;
    milestones: Record<FactorToken, string>;
    savedRoles: string; savedRolesSub: string;
    applications: string; applicationsSub: string;
    progress: string; progressSub: string;
    suggestedEyebrow: string; suggestedTitle: string;
    actions: Record<NextActionKey, { title: string; body: string; cta: string }>;
    loading: string; loadError: string; retry: string;
    missionEmptyTitle: string;
    goalRoleCity: (role: string, city: string) => string;
    goalRoleOnly: (role: string) => string;
    goalCityOnly: (city: string) => string;
}> = {
    en: {
        eyebrow: "Overview", title: "Good to see you.",
        intro: "A quiet overview of your workspace — Rico keeps it current as you go.",
        goalEyebrow: "Current goal",
        goalSubtitle: "Everything Rico surfaces should serve this.",
        goalEdit: "Edit goal",
        progressAria: "Goal progress",
        milestones: {
            cv_uploaded: "CV uploaded",
            roles_set: "Target roles set",
            locations_set: "Preferred cities set",
            pipeline_active: "First jobs tracked",
        },
        savedRoles: "Saved roles", savedRolesSub: "curated by Rico",
        applications: "Applications", applicationsSub: "sent so far",
        progress: "Progress", progressSub: "mission readiness",
        suggestedEyebrow: "Suggested next",
        suggestedTitle: "What moves this forward",
        actions: {
            upload_cv: { title: "Upload your CV", body: "Rico can't score job matches without it.", cta: "Upload" },
            set_goals: { title: "Set your target roles and cities", body: "Tell Rico what to search for and where.", cta: "Open profile" },
            search_jobs: { title: "Search for jobs with Rico", body: "Start the conversation and save roles that interest you.", cta: "Open Command" },
            review_applications: { title: "Review your applications", body: "See every open thread and what needs a follow-up.", cta: "Open applications" },
            keep_going: { title: "Continue with Rico", body: "Return to the conversation and keep the search moving.", cta: "Open Command" },
            review_profile: { title: "Review your profile", body: "Check the working portrait Rico reads about you.", cta: "Open profile" },
        },
        loading: "Loading your workspace…",
        loadError: "Couldn't load your workspace right now.",
        retry: "Retry",
        missionEmptyTitle: "Set your first mission",
        goalRoleCity: (role, city) => `Find a ${role} role in ${city}`,
        goalRoleOnly: (role) => `Find a ${role} role in the UAE`,
        goalCityOnly: (city) => `Find a job in ${city}`,
    },
    ar: {
        eyebrow: "نظرة عامة", title: "سعيدٌ برؤيتك.",
        intro: "نظرةٌ هادئة على مساحة عملك — يبقيها ريكو محدّثةً أولًا بأول.",
        goalEyebrow: "الهدف الحالي",
        goalSubtitle: "كل ما يعرضه ريكو يجب أن يخدم هذا الهدف.",
        goalEdit: "تعديل الهدف",
        progressAria: "تقدّم الهدف",
        milestones: {
            cv_uploaded: "السيرة مرفوعة",
            roles_set: "الأدوار المستهدفة محدّدة",
            locations_set: "المدن المفضّلة محدّدة",
            pipeline_active: "أولى الوظائف مُتتبَّعة",
        },
        savedRoles: "الأدوار المحفوظة", savedRolesSub: "منسّقة من ريكو",
        applications: "الطلبات", applicationsSub: "أُرسلت حتى الآن",
        progress: "التقدّم", progressSub: "جاهزية المهمّة",
        suggestedEyebrow: "الخطوة التالية",
        suggestedTitle: "ما الذي يدفع هدفك للأمام",
        actions: {
            upload_cv: { title: "ارفع سيرتك الذاتية", body: "لا يستطيع ريكو تقييم المطابقات دونها.", cta: "رفع" },
            set_goals: { title: "حدّد أدوارك ومدنك المستهدفة", body: "أخبر ريكو عمّا يبحث وأين.", cta: "افتح الملف" },
            search_jobs: { title: "ابحث عن وظائف مع ريكو", body: "ابدأ المحادثة واحفظ الأدوار التي تهمّك.", cta: "افتح الأوامر" },
            review_applications: { title: "راجع طلباتك", body: "اطّلع على كل طلب مفتوح وما يحتاج متابعة.", cta: "افتح الطلبات" },
            keep_going: { title: "تابع مع ريكو", body: "عُد إلى المحادثة وواصل البحث.", cta: "افتح الأوامر" },
            review_profile: { title: "راجع ملفك", body: "تفقّد الصورة المهنية التي يقرأها ريكو عنك.", cta: "افتح الملف" },
        },
        loading: "جارٍ تحميل مساحة عملك…",
        loadError: "تعذّر تحميل مساحة عملك الآن.",
        retry: "أعد المحاولة",
        missionEmptyTitle: "حدّد مهمّتك الأولى",
        goalRoleCity: (role, city) => `إيجاد دور ${role} في ${city}`,
        goalRoleOnly: (role) => `إيجاد دور ${role} في الإمارات`,
        goalCityOnly: (city) => `إيجاد وظيفة في ${city}`,
    },
};

/** Localized goal title from the STRUCTURED mission fields (mirrors the
 *  server's _build_goal derivation — same truth, bilingual presentation). */
export function deriveGoalTitle(mission: MissionState | null, lang: Lang): string {
    const t = T[lang];
    const role = mission?.target_roles?.[0]?.trim();
    const city = mission?.target_locations?.[0]?.trim();
    if (role && city) return t.goalRoleCity(role, city);
    if (role) return t.goalRoleOnly(role);
    if (city) return t.goalCityOnly(city);
    return t.missionEmptyTitle;
}

type Palette = ReturnType<typeof useWorkspaceTheme>;

function StatPlate({ c, label, sub, value }: { c: Palette; label: string; sub: string; value: string | number }) {
    return (
        <div className="rounded-[4px] p-5 flex items-start justify-between" style={{ background: c.panel, border: `1px solid ${c.hair}` }}>
            <div>
                <Mono style={{ color: c.ink55 }}>{label}</Mono>
                <p className="mt-1 text-[0.9rem]" style={{ color: c.ink40 }}>{sub}</p>
            </div>
            <span style={{ fontFamily: SERIF, fontSize: "2rem", lineHeight: 1, color: c.ink }}>{value}</span>
        </div>
    );
}

function MilestonePill({ c, done, label }: { c: Palette; done: boolean; label: string }) {
    return (
        <li
            data-testid="dashboard-milestone"
            data-done={done ? "true" : "false"}
            className="flex items-center gap-2.5 rounded-[8px] px-3 py-2"
            style={{ background: c.inset, border: `1px solid ${c.hair}` }}
        >
            {done ? (
                <span aria-hidden="true" className="inline-flex items-center justify-center shrink-0" style={{ width: 16, height: 16, borderRadius: 999, background: c.red }}>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke={c.panel} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 6L9 17l-5-5" /></svg>
                </span>
            ) : (
                <span aria-hidden="true" className="inline-flex shrink-0" style={{ width: 16, height: 16, borderRadius: 999, border: `1.5px dashed ${c.ink40}` }} />
            )}
            <span className="text-[0.9rem]" style={{ color: done ? c.ink : c.ink55 }}>{label}</span>
        </li>
    );
}

export function DashboardAtelier() {
    const { language } = useLanguage();
    const c = useWorkspaceTheme();
    const t = T[language];
    const [mission, setMission] = useState<MissionState | null>(null);
    const [state, setState] = useState<"loading" | "ready" | "error">("loading");

    const load = useCallback(async () => {
        setState("loading");
        try {
            setMission(await getMission());
            setState("ready");
        } catch {
            setState("error");
        }
    }, []);

    useEffect(() => {
        const id = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(id);
    }, [load]);

    const pct = Math.max(0, Math.min(100, Math.round(mission?.progress_score ?? 0)));
    const missing = new Set(mission?.missing_factors ?? []);
    const nextActions = deriveNextActions(mission);
    const goalTitle = deriveGoalTitle(mission, language);
    const rolesLine = [
        ...(mission?.target_roles ?? []),
        ...(mission?.target_locations ?? []),
    ].join(" · ");

    return (
        <div>
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
                <div>
                    <Mono style={{ color: c.ink55 }}>{t.eyebrow}</Mono>
                    <h1 className="mt-2 text-[2.4rem] sm:text-[3rem] leading-[0.98] font-normal" style={{ fontFamily: SERIF, color: c.ink }}>{t.title}</h1>
                </div>
            </div>
            <div className="my-6 h-px" style={{ background: c.hair }} aria-hidden="true" />
            <p className="max-w-2xl text-[1.02rem] leading-relaxed" style={{ color: c.ink70 }}>{t.intro}</p>

            {state === "loading" && (
                <p className="mt-10" style={{ color: c.ink40 }} aria-busy="true">{t.loading}</p>
            )}

            {/* Explicit failure state — never zeroed panels pretending to be data. */}
            {state === "error" && (
                <div role="alert" data-testid="dashboard-error" className="mt-10 flex items-center gap-4">
                    <p style={{ color: c.ink70 }}>{t.loadError}</p>
                    <button
                        type="button"
                        data-testid="dashboard-retry"
                        onClick={() => void load()}
                        className="rounded-[6px] px-3.5 py-1.5 text-sm font-semibold"
                        style={{ border: `1px solid ${c.hair}`, color: c.ink, background: "transparent", cursor: "pointer" }}
                    >
                        {t.retry}
                    </button>
                </div>
            )}

            {state === "ready" && (
                <>
                    {/* Goal panel + stat plates */}
                    <div className="mt-10 grid lg:grid-cols-[1.6fr_1fr] gap-4">
                        <section aria-labelledby="dashboard-goal-title" className="rounded-[4px] p-6 sm:p-7" style={{ background: c.panel, border: `1px solid ${c.hair}` }}>
                            <Mono style={{ color: c.ink55 }}>{t.goalEyebrow}</Mono>
                            <h2 id="dashboard-goal-title" data-testid="dashboard-goal-title" className="mt-2 text-[1.7rem] sm:text-[2rem] leading-[1.1] font-normal" style={{ fontFamily: SERIF, color: c.ink }}>
                                {goalTitle}
                            </h2>
                            {rolesLine && (
                                <p className="mt-1.5 text-[0.95rem]" style={{ color: c.ink55 }} data-testid="dashboard-goal-scope">{rolesLine}</p>
                            )}
                            <p className="mt-1 text-[0.9rem]" style={{ color: c.ink40 }}>{t.goalSubtitle}</p>

                            <div className="mt-5 flex items-center gap-4">
                                <div
                                    role="progressbar"
                                    aria-valuemin={0}
                                    aria-valuemax={100}
                                    aria-valuenow={pct}
                                    aria-label={t.progressAria}
                                    className="h-1.5 flex-1 rounded-full overflow-hidden"
                                    style={{ background: c.track }}
                                >
                                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: c.red }} />
                                </div>
                                <span style={{ fontFamily: SERIF, fontSize: "1.9rem", lineHeight: 1, color: c.ink }}>{pct}%</span>
                            </div>

                            <ul className="mt-5 grid sm:grid-cols-2 gap-2.5 list-none p-0 m-0">
                                {FACTOR_TOKENS.map((token) => (
                                    <MilestonePill key={token} c={c} done={!missing.has(token)} label={t.milestones[token]} />
                                ))}
                            </ul>

                            <Link
                                href="/profile?section=goals"
                                data-testid="dashboard-goal-edit"
                                className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold"
                                style={{ color: c.ink, borderBottom: `1px solid ${c.ink}`, textDecoration: "none", paddingBottom: 1 }}
                            >
                                {t.goalEdit} <span aria-hidden="true">{language === "ar" ? "←" : "→"}</span>
                            </Link>
                        </section>

                        {/* Stat plates — real counters */}
                        <div className="flex flex-col gap-4">
                            <StatPlate c={c} label={t.savedRoles} sub={t.savedRolesSub} value={mission?.jobs_saved ?? 0} />
                            <StatPlate c={c} label={t.applications} sub={t.applicationsSub} value={mission?.applications_sent ?? 0} />
                            <StatPlate c={c} label={t.progress} sub={t.progressSub} value={`${pct}%`} />
                        </div>
                    </div>

                    {/* Suggested next — derived from real mission state, max 3 */}
                    <section aria-labelledby="dashboard-next-title" className="mt-12">
                        <Mono style={{ color: c.ink55 }}>{t.suggestedEyebrow}</Mono>
                        <h2 id="dashboard-next-title" className="mt-2 text-[1.15rem] font-normal" style={{ fontFamily: SERIF, color: c.ink }}>{t.suggestedTitle}</h2>
                        <ul className="mt-4 grid sm:grid-cols-2 lg:grid-cols-3 gap-3 list-none p-0 m-0">
                            {nextActions.map((key) => {
                                const a = t.actions[key];
                                return (
                                    <li key={key}>
                                        <Link
                                            href={NEXT_ACTION_HREF[key]}
                                            data-testid="dashboard-next-action"
                                            data-action={key}
                                            className="wsx-action rounded-[4px] p-5 block h-full"
                                            style={{ background: c.panel, border: `1px solid ${c.hair}`, textDecoration: "none" }}
                                        >
                                            <h3 className="text-[1.15rem] font-normal" style={{ fontFamily: SERIF, color: c.ink }}>{a.title}</h3>
                                            <p className="mt-1.5 text-[0.9rem] leading-snug" style={{ color: c.ink55 }}>{a.body}</p>
                                            <span className="mt-3 inline-flex items-center gap-1.5 text-[0.8rem] font-semibold" style={{ color: c.red }}>
                                                {a.cta} <span aria-hidden="true">{language === "ar" ? "←" : "→"}</span>
                                            </span>
                                        </Link>
                                    </li>
                                );
                            })}
                        </ul>
                    </section>
                </>
            )}
        </div>
    );
}
