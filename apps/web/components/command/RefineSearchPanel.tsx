"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import { useState } from "react";

/**
 * RefineSearchPanel — the structured refinement flow behind the
 * "Refine search" action card (P1, 2026-07-19).
 *
 * UI actions and natural language stay strictly separate: the card is an
 * `open_drawer` action, this panel collects structured inputs (role + city),
 * and only the FINAL composed search query is sent as a normal, user-visible
 * chat message. The LLM never sees any UI wording ("Refine search" used to be
 * sent verbatim and got parsed as a job role).
 */

const CITY_DEFS: { key: TranslationKey; id: string }[] = [
    { key: "cmdRefineCityAllUae", id: "all-uae" },
    { key: "cmdRefineCityDubai", id: "dubai" },
    { key: "cmdRefineCityAbuDhabi", id: "abu-dhabi" },
    { key: "cmdRefineCitySharjah", id: "sharjah" },
    { key: "cmdRefineCityAjman", id: "ajman" },
];

export function buildRefinedQuery(
    language: "en" | "ar",
    role: string,
    cityLabel: string | null,
): string {
    const cleanRole = role.trim();
    if (language === "ar") {
        return cityLabel
            ? `ابحث عن وظائف ${cleanRole} في ${cityLabel}`
            : `ابحث عن وظائف ${cleanRole} في الإمارات`;
    }
    return cityLabel
        ? `Find ${cleanRole} jobs in ${cityLabel}`
        : `Find ${cleanRole} jobs in the UAE`;
}

export function RefineSearchPanel({
    initialRole,
    onSubmit,
    onClose,
    disabled = false,
}: {
    initialRole: string;
    onSubmit: (query: string) => void;
    onClose: () => void;
    disabled?: boolean;
}) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const [role, setRole] = useState(initialRole);
    const [cityId, setCityId] = useState<string>("all-uae");

    const canSubmit = !disabled && role.trim().length > 0;

    function handleSubmit() {
        if (!canSubmit) return;
        const city = CITY_DEFS.find((c) => c.id === cityId);
        const cityLabel = city && city.id !== "all-uae" ? t(city.key) : null;
        onSubmit(buildRefinedQuery(language, role, cityLabel));
        onClose();
    }

    return (
        <div
            data-testid="refine-search-panel"
            role="form"
            aria-label={t("cmdRefineTitle")}
            className="mb-3 rounded-2xl border border-gold/30 bg-surface-glass p-4"
        >
            <div className="mb-3 flex items-center justify-between gap-3">
                <span className="text-[12px] font-medium tracking-wide text-gold">
                    {t("cmdRefineTitle")}
                </span>
                <button
                    type="button"
                    data-testid="refine-cancel"
                    onClick={onClose}
                    className="text-[11px] text-text-muted transition-colors hover:text-rico-text rico-focus-strong"
                >
                    {t("cmdRefineCancel")}
                </button>
            </div>

            <label className="mb-2 block">
                <span className="mb-1 block text-[10px] uppercase tracking-wider text-text-muted">
                    {t("cmdRefineRoleLabel")}
                </span>
                <input
                    type="text"
                    data-testid="refine-role-input"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === "Enter") {
                            e.preventDefault();
                            handleSubmit();
                        }
                    }}
                    placeholder={t("cmdRefineRolePlaceholder")}
                    disabled={disabled}
                    className="w-full rounded-xl border border-border-soft bg-transparent px-3 py-2 text-[13px] text-rico-text placeholder:text-text-muted focus:border-gold/50 focus:outline-none"
                />
            </label>

            <span className="mb-1 block text-[10px] uppercase tracking-wider text-text-muted">
                {t("cmdRefineCityLabel")}
            </span>
            <div className="mb-3 flex flex-wrap gap-1.5" role="radiogroup" aria-label={t("cmdRefineCityLabel")}>
                {CITY_DEFS.map((c) => {
                    const selected = cityId === c.id;
                    return (
                        <button
                            type="button"
                            key={c.id}
                            role="radio"
                            aria-checked={selected}
                            data-testid={`refine-city-${c.id}`}
                            onClick={() => setCityId(c.id)}
                            disabled={disabled}
                            className={
                                selected
                                    ? "rounded-xl border border-gold/60 bg-gold/10 px-3 py-1.5 text-[11px] text-gold rico-focus-strong"
                                    : "rounded-xl border border-border-soft px-3 py-1.5 text-[11px] text-text-secondary transition-colors hover:border-gold/40 hover:text-gold rico-focus-strong"
                            }
                        >
                            {t(c.key)}
                        </button>
                    );
                })}
            </div>

            <button
                type="button"
                data-testid="refine-submit"
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="rounded-xl border border-gold/50 bg-gold/10 px-4 py-2 text-[12px] font-medium text-gold transition-colors hover:bg-gold/20 disabled:cursor-not-allowed disabled:opacity-50 rico-focus-strong"
            >
                {t("cmdRefineSubmit")}
            </button>
        </div>
    );
}
