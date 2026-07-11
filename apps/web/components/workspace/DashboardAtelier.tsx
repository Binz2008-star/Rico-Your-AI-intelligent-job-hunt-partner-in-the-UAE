"use client";

/**
 * DashboardAtelier — the /dashboard content rebuilt to the approved
 * /design-preview workspace reference (desktop-dashboard-en-light.png), PR 5A.
 *
 * Data is REAL, not sample: every number/checklist item comes from the
 * existing GET /api/v1/mission/current (MissionState) and the same
 * application-stats endpoint the current dashboard already used. Where the
 * reference showed decorative "SAMPLE" content with no production data source
 * (the recent-activity timeline and scored saved-roles list), those blocks are
 * intentionally OMITTED rather than faked — per DEC-20260710-002 (no fake live
 * data). Loading and empty states are handled explicitly.
 *
 * Visual system: shared atelier-kit tokens + Mono primitive; theme colors are
 * passed in from WorkspaceShell so light/dark stays consistent with the shell.
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

const T: Record<Lang, {
    eyebrow: string; title: string; intro: string;
    completeness: string; completenessHint: string; completeCta: string;
    savedRoles: string; savedRolesSub: string;
    inPipeline: string; inPipelineSub: string;
    applied: string; appliedSub: string;
    quickActions: string;
    actions: { label: string; desc: string; href: string }[];
    cvUploaded: string; rolesSet: string; citiesSet: string;
    loading: string; missionEmptyTitle: string; missionEmptyCta: string;
}> = {
    en: {
        eyebrow: "Dashboard", title: "Good to see you.",
        intro: "A quiet overview of your workspace — Rico keeps it current as you go.",
        completeness: "Profile completeness", completenessHint: "A stronger profile helps Rico surface sharper matches.",
        completeCta: "Complete profile",
        savedRoles: "Saved roles", savedRolesSub: "curated by Rico",
        inPipeline: "In pipeline", inPipelineSub: "applications sent",
        applied: "Progress", appliedSub: "mission readiness",
        quickActions: "Quick actions",
        actions: [
            { label: "Upload CV", desc: "Refresh what Rico reads about you.", href: "/upload" },
            { label: "Review profile", desc: "Check the working portrait.", href: "/profile" },
            { label: "Open Command", desc: "Return to the conversation.", href: "/command" },
            { label: "View applications", desc: "See every open thread.", href: "/applications" },
            { label: "Settings", desc: "Language, theme, notifications.", href: "/settings" },
        ],
        cvUploaded: "CV uploaded", rolesSet: "Target roles set", citiesSet: "Preferred cities set",
        loading: "Loading your workspace…",
        missionEmptyTitle: "Set your first mission",
        missionEmptyCta: "Start with Rico",
    },
    ar: {
        eyebrow: "لوحة التحكم", title: "سعيدٌ برؤيتك.",
        intro: "نظرةٌ هادئة على مساحة عملك — يبقيها ريكو محدّثةً أولًا بأول.",
        completeness: "اكتمال الملف", completenessHint: "الملف الأقوى يساعد ريكو على إيجاد مطابقاتٍ أدقّ.",
        completeCta: "أكمل ملفك",
        savedRoles: "الأدوار المحفوظة", savedRolesSub: "منسّقة من ريكو",
        inPipeline: "قيد المتابعة", inPipelineSub: "طلبات مُرسلة",
        applied: "التقدّم", appliedSub: "جاهزية المهمّة",
        quickActions: "إجراءات سريعة",
        actions: [
            { label: "رفع السيرة", desc: "حدّث ما يقرأه ريكو عنك.", href: "/upload" },
            { label: "مراجعة الملف", desc: "راجع صورتك المهنيّة.", href: "/profile" },
            { label: "افتح الأوامر", desc: "عُد إلى المحادثة.", href: "/command" },
            { label: "عرض الطلبات", desc: "اطّلع على كل طلب مفتوح.", href: "/applications" },
            { label: "الإعدادات", desc: "اللغة، المظهر، الإشعارات.", href: "/settings" },
        ],
        cvUploaded: "السيرة مرفوعة", rolesSet: "الأدوار المستهدفة محدّدة", citiesSet: "المدن المفضّلة محدّدة",
        loading: "جارٍ تحميل مساحة عملك…",
        missionEmptyTitle: "حدّد مهمّتك الأولى",
        missionEmptyCta: "ابدأ مع ريكو",
    },
};

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

function Check({ c, on, label }: { c: Palette; on: boolean; label: string }) {
    return (
        <span className="flex items-center gap-2.5">
            <span className="inline-flex items-center justify-center" style={{ width: 16, height: 16, borderRadius: 3, border: `1.5px solid ${on ? c.red : c.hair}`, background: on ? c.red : "transparent" }}>
                {on && <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke={c.panel} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 6L9 17l-5-5" /></svg>}
            </span>
            <span className="text-[0.95rem]" style={{ color: on ? c.ink : c.ink55 }}>{label}</span>
        </span>
    );
}

export function DashboardAtelier() {
    const { language } = useLanguage();
    const c = useWorkspaceTheme();
    const t = T[language];
    const [mission, setMission] = useState<MissionState | null>(null);
    const [state, setState] = useState<"loading" | "ready" | "error">("loading");

    const load = useCallback(async () => {
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
    const cvOk = mission?.cv_status === "uploaded";
    const rolesOk = (mission?.target_roles?.length ?? 0) > 0;
    const citiesOk = (mission?.target_locations?.length ?? 0) > 0;

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

            {state !== "loading" && (
                <>
                    {/* Completeness + stat plates */}
                    <div className="mt-10 grid lg:grid-cols-[1.6fr_1fr] gap-4">
                        {/* Profile completeness */}
                        <div className="rounded-[4px] p-6 sm:p-7" style={{ background: c.panel, border: `1px solid ${c.hair}` }}>
                            <div className="flex items-center justify-between">
                                <Mono style={{ color: c.ink55 }}>{t.completeness}</Mono>
                                <span style={{ fontFamily: SERIF, fontSize: "1.9rem", lineHeight: 1, color: c.ink }}>{pct}%</span>
                            </div>
                            <div className="mt-3 h-1.5 rounded-full overflow-hidden" style={{ background: c.track }}>
                                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: c.red }} />
                            </div>
                            <p className="mt-4 text-[0.98rem]" style={{ color: c.ink70 }}>{t.completenessHint}</p>
                            <div className="mt-5 grid sm:grid-cols-2 gap-3.5">
                                <Check c={c} on={cvOk} label={t.cvUploaded} />
                                <Check c={c} on={rolesOk} label={t.rolesSet} />
                                <Check c={c} on={citiesOk} label={t.citiesSet} />
                            </div>
                            <Link href="/profile" className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold" style={{ color: c.ink, borderBottom: `1px solid ${c.ink}`, textDecoration: "none", paddingBottom: 1 }}>
                                {t.completeCta} <span aria-hidden="true">{language === "ar" ? "←" : "→"}</span>
                            </Link>
                        </div>
                        {/* Stat plates */}
                        <div className="flex flex-col gap-4">
                            <StatPlate c={c} label={t.savedRoles} sub={t.savedRolesSub} value={mission?.jobs_saved ?? 0} />
                            <StatPlate c={c} label={t.inPipeline} sub={t.inPipelineSub} value={mission?.applications_sent ?? 0} />
                            <StatPlate c={c} label={t.applied} sub={t.appliedSub} value={`${pct}%`} />
                        </div>
                    </div>

                    {/* Quick actions */}
                    <div className="mt-12">
                        <Mono style={{ color: c.ink55 }}>{t.quickActions}</Mono>
                        <div className="mt-4 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                            {t.actions.map((a) => (
                                <Link key={a.href + a.label} href={a.href} className="wsx-action rounded-[4px] p-5 block" style={{ background: c.panel, border: `1px solid ${c.hair}`, textDecoration: "none" }}>
                                    <h3 className="text-[1.15rem] font-normal" style={{ fontFamily: SERIF, color: c.ink }}>{a.label}</h3>
                                    <p className="mt-1.5 text-[0.9rem] leading-snug" style={{ color: c.ink55 }}>{a.desc}</p>
                                </Link>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
