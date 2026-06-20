"use client";

import { fetchProfile, type ProfileResponse } from "@/lib/api";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import { useEffect, useState } from "react";

const DISMISS_KEY = "rico_profile_nudge_dismissed";
const NUDGE_THRESHOLD = 80;

interface MissingField {
    key: string;
    labelKey: "profileNudgeMissingCv" | "profileNudgeMissingRoles" | "profileNudgeMissingCities";
}

function getMissingFields(profile: ProfileResponse): MissingField[] {
    const missing: MissingField[] = [];
    // CV is inferred: CV parser populates skills and years_experience
    const likelyCvMissing = !profile.skills?.length && profile.years_experience == null && !profile.current_role;
    if (likelyCvMissing) missing.push({ key: "cv", labelKey: "profileNudgeMissingCv" });
    if (!profile.target_roles?.length) missing.push({ key: "roles", labelKey: "profileNudgeMissingRoles" });
    if (!profile.preferred_cities?.length) missing.push({ key: "cities", labelKey: "profileNudgeMissingCities" });
    return missing;
}

export function ProfileCompletionBanner() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const [visible, setVisible] = useState(false);
    const [score, setScore] = useState<number>(0);
    const [missing, setMissing] = useState<MissingField[]>([]);

    useEffect(() => {
        if (typeof sessionStorage !== "undefined" && sessionStorage.getItem(DISMISS_KEY) === "1") {
            return;
        }
        fetchProfile()
            .then((data) => {
                if (!data.profile_exists) return;
                const completeness = data.completeness_score ?? 0;
                if (completeness >= NUDGE_THRESHOLD) return;
                setScore(Math.round(completeness * 100));
                setMissing(getMissingFields(data));
                setVisible(true);
            })
            .catch(() => {});
    }, []);

    const dismiss = () => {
        if (typeof sessionStorage !== "undefined") {
            sessionStorage.setItem(DISMISS_KEY, "1");
        }
        setVisible(false);
    };

    if (!visible) return null;

    return (
        <div className="mb-6 rounded-xl border border-amber-500/20 bg-amber-500/5 px-5 py-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                    <span className="text-amber-400 text-sm font-semibold">{t("profileNudgeTitle")}</span>
                    <span className="text-xs text-amber-400/60 font-mono">{score}%</span>
                </div>
                <p className="text-xs text-on-surface-variant leading-relaxed">{t("profileNudgeDesc")}</p>
                {missing.length > 0 && (
                    <ul className="mt-2 flex flex-wrap gap-2">
                        {missing.map((f: MissingField) => (
                            <li
                                key={f.key}
                                className="inline-flex items-center gap-1 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-0.5 text-[11px] text-amber-300"
                            >
                                <span className="text-amber-400">·</span>
                                {t(f.labelKey)}
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div className="flex items-center gap-3 flex-shrink-0">
                <Link
                    href="/onboarding"
                    className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-xs font-semibold text-[#0a0a1a] hover:bg-amber-400 transition-colors"
                >
                    {t("profileNudgeCta")}
                </Link>
                <button
                    onClick={dismiss}
                    className="text-xs text-on-surface-variant hover:text-on-surface transition-colors"
                    aria-label={t("profileNudgeDismiss")}
                >
                    {t("profileNudgeDismiss")}
                </button>
            </div>
        </div>
    );
}
