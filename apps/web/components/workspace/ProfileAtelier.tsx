"use client";

/**
 * ProfileAtelier — /profile rebuilt to the approved /design-preview workspace
 * reference (en-profile-desktop.png), PR 5B. A read "working portrait" with a
 * single Edit toggle that reveals inline editing (owner decision: preserve the
 * existing inline-edit capability, not chat-only).
 *
 * Data + mutations are REAL: fetchProfile() / updateProfile() — the same
 * endpoints the previous /profile used. Edit mode batches only the CHANGED
 * fields into one PATCH (the API accepts partial payloads), then re-fetches.
 * Reference sections with no production data source (experience timeline,
 * languages, education) are OMITTED, not faked, per DEC-20260710-002.
 *
 * Rendered inside WorkspaceShell (Shell C); colors come from the shared
 * WorkspaceThemeContext so light/dark stays consistent with the shell.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { Mono } from "@/components/atelier-kit/primitives";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import {
    ApiError,
    fetchProfile,
    updateProfile,
    type ProfileResponse,
    type ProfileUpdatePayload,
} from "@/lib/api";

const SERIF = ATELIER_FONT.serif;

type Lang = "en" | "ar";

const T: Record<Lang, {
    eyebrow: string; title: string;
    edit: string; save: string; saving: string; cancel: string;
    identity: string; skills: string; targetRoles: string; preferences: string;
    role: string; industry: string; location: string; salary: string; experience: string; years: string;
    name: string; namePh: string; rolePh: string; addSkill: string; addRole: string; addCity: string; addIndustry: string;
    empty: string; none: string;
    loading: string; errTitle: string; errBody: string; retry: string;
    saved: string; saveFail: string;
    completeness: string;
}> = {
    en: {
        eyebrow: "CV Profile", title: "Your working portrait.",
        edit: "Edit", save: "Save changes", saving: "Saving…", cancel: "Cancel",
        identity: "Identity", skills: "Skills", targetRoles: "Target roles", preferences: "Preferences",
        role: "Current role", industry: "Industry", location: "Preferred cities", salary: "Salary expectation", experience: "Experience", years: "years",
        name: "Name", namePh: "Your name", rolePh: "e.g. Senior Product Manager", addSkill: "Add a skill", addRole: "Add a target role", addCity: "Add a city", addIndustry: "Add an industry",
        empty: "Your profile is empty. Upload your CV or edit to add details.", none: "Not set",
        loading: "Loading your profile…", errTitle: "We couldn't load your profile", errBody: "Please try again in a moment.", retry: "Retry",
        saved: "Profile saved.", saveFail: "Could not save — please try again.",
        completeness: "complete",
    },
    ar: {
        eyebrow: "الملف المهني", title: "صورتك المهنيّة.",
        edit: "تعديل", save: "حفظ التغييرات", saving: "جارٍ الحفظ…", cancel: "إلغاء",
        identity: "الهوية", skills: "المهارات", targetRoles: "الأدوار المستهدفة", preferences: "التفضيلات",
        role: "الدور الحالي", industry: "المجال", location: "المدن المفضّلة", salary: "الراتب المتوقّع", experience: "الخبرة", years: "سنوات",
        name: "الاسم", namePh: "اسمك", rolePh: "مثال: مدير منتج أول", addSkill: "أضف مهارة", addRole: "أضف دوراً مستهدفاً", addCity: "أضف مدينة", addIndustry: "أضف مجالاً",
        empty: "ملفك فارغ. ارفع سيرتك أو عدّل لإضافة التفاصيل.", none: "غير محدّد",
        loading: "جارٍ تحميل ملفك…", errTitle: "تعذّر تحميل ملفك", errBody: "أعد المحاولة بعد قليل.", retry: "إعادة",
        saved: "تم حفظ الملف.", saveFail: "تعذّر الحفظ — أعد المحاولة.",
        completeness: "مكتمل",
    },
};

type Palette = ReturnType<typeof useWorkspaceTheme>;

/* ── Editable chip list ─────────────────────────────────────────────────── */
function TagEditor({ c, values, placeholder, onChange }: { c: Palette; values: string[]; placeholder: string; onChange: (next: string[]) => void }) {
    const [input, setInput] = useState("");
    const add = () => {
        const v = input.trim();
        if (v && !values.includes(v)) onChange([...values, v]);
        setInput("");
    };
    return (
        <div className="flex flex-wrap items-center gap-1.5">
            {values.map((v) => (
                <span key={v} className="inline-flex items-center gap-1.5 rounded-[3px] px-2 py-1 text-[0.85rem]" style={{ background: c.inset, color: c.ink70, border: `1px solid ${c.hair}` }}>
                    {v}
                    <button type="button" aria-label={`remove ${v}`} onClick={() => onChange(values.filter((x) => x !== v))} style={{ color: c.ink40, cursor: "pointer", lineHeight: 1 }}>×</button>
                </span>
            ))}
            <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(); } else if (e.key === "Backspace" && !input && values.length) { onChange(values.slice(0, -1)); } }}
                onBlur={add}
                placeholder={placeholder}
                className="min-w-[8rem] flex-1 bg-transparent py-1 text-[0.9rem] outline-none"
                style={{ color: c.ink, borderBottom: `1px solid ${c.hair}` }}
            />
        </div>
    );
}

function Chips({ c, values, empty }: { c: Palette; values: string[]; empty: string }) {
    if (!values.length) return <p className="text-[0.9rem]" style={{ color: c.ink40 }}>{empty}</p>;
    return (
        <div className="flex flex-wrap gap-1.5">
            {values.map((v) => (
                <span key={v} className="rounded-[3px] px-2.5 py-1 text-[0.85rem]" style={{ background: c.inset, color: c.ink70, border: `1px solid ${c.hair}` }}>{v}</span>
            ))}
        </div>
    );
}

function Section({ c, label, children }: { c: Palette; label: string; children: React.ReactNode }) {
    return (
        <section className="mt-8">
            <Mono style={{ color: c.ink55 }}>{label}</Mono>
            <div className="mt-3">{children}</div>
        </section>
    );
}

/* Edit draft shape — only the fields this portrait surfaces. */
interface Draft {
    name: string;
    current_role: string;
    industries: string[];
    target_roles: string[];
    preferred_cities: string[];
    skills: string[];
    salary_expectation_aed: string;
    years_experience: string;
}

function toDraft(p: ProfileResponse): Draft {
    return {
        name: p.name ?? "",
        current_role: p.current_role ?? "",
        industries: p.industries ?? [],
        target_roles: p.target_roles ?? [],
        preferred_cities: p.preferred_cities ?? [],
        skills: p.skills ?? [],
        salary_expectation_aed: p.salary_expectation_aed != null ? String(p.salary_expectation_aed) : "",
        years_experience: p.years_experience != null ? String(p.years_experience) : "",
    };
}

export function ProfileAtelier() {
    const { language } = useLanguage();
    const c = useWorkspaceTheme();
    const t = T[language];

    const [profile, setProfile] = useState<ProfileResponse | null>(null);
    const [state, setState] = useState<"loading" | "ready" | "error">("loading");
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState<Draft | null>(null);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState<string | null>(null);

    const load = useCallback(async () => {
        setState("loading");
        try {
            const data = await fetchProfile();
            setProfile(data);
            setState("ready");
        } catch (err) {
            setState("error");
            if (err instanceof ApiError && err.statusCode === 401) {
                window.location.href = "/login?next=%2Fprofile";
            }
        }
    }, []);

    useEffect(() => {
        const id = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(id);
    }, [load]);

    const startEdit = () => { if (profile) { setDraft(toDraft(profile)); setEditing(true); setNotice(null); } };
    const cancelEdit = () => { setEditing(false); setDraft(null); setNotice(null); };

    const save = useCallback(async () => {
        if (!profile || !draft) return;
        // Build a partial payload of only the CHANGED fields.
        const base = toDraft(profile);
        const payload: ProfileUpdatePayload = {};
        if (draft.name.trim() !== base.name) payload.name = draft.name.trim();
        if (draft.current_role.trim() !== base.current_role) payload.current_role = draft.current_role.trim();
        // Note: industries has no updateProfile field, so it is display-only (not edited here).
        if (JSON.stringify(draft.target_roles) !== JSON.stringify(base.target_roles)) payload.target_roles = draft.target_roles;
        if (JSON.stringify(draft.preferred_cities) !== JSON.stringify(base.preferred_cities)) payload.preferred_cities = draft.preferred_cities;
        if (JSON.stringify(draft.skills) !== JSON.stringify(base.skills)) payload.skills = draft.skills;
        const salaryNum = draft.salary_expectation_aed.trim() === "" ? null : Number(draft.salary_expectation_aed);
        if (salaryNum != null && Number.isFinite(salaryNum) && String(salaryNum) !== base.salary_expectation_aed) payload.salary_expectation_aed = salaryNum;
        const yearsNum = draft.years_experience.trim() === "" ? null : Number(draft.years_experience);
        if (yearsNum != null && Number.isFinite(yearsNum) && String(yearsNum) !== base.years_experience) payload.years_experience = yearsNum;

        if (Object.keys(payload).length === 0) { setEditing(false); setDraft(null); return; }

        setSaving(true);
        setNotice(null);
        try {
            await updateProfile(payload);
            setEditing(false);
            setDraft(null);
            setNotice(t.saved);
            await load();
        } catch {
            setNotice(t.saveFail);
        } finally {
            setSaving(false);
        }
    }, [profile, draft, load, t]);

    const completeness = useMemo(() => {
        const s = profile?.completeness_score;
        return s != null ? Math.round(s <= 1 ? s * 100 : s) : null;
    }, [profile]);

    const inputStyle: React.CSSProperties = { color: c.ink, background: c.inset, border: `1px solid ${c.hair}`, borderRadius: 3, padding: "8px 10px", fontSize: "0.95rem", width: "100%", outline: "none" };

    return (
        <div>
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
                <div>
                    <Mono style={{ color: c.ink55 }}>{t.eyebrow}</Mono>
                    <h1 className="mt-2 text-[2.4rem] sm:text-[3rem] leading-[0.98] font-normal" style={{ fontFamily: SERIF, color: c.ink }}>{t.title}</h1>
                </div>
                {state === "ready" && (
                    <div className="flex items-center gap-3 shrink-0">
                        {completeness != null && <Mono style={{ color: c.ink40 }}>{completeness}% {t.completeness}</Mono>}
                        {!editing ? (
                            <button type="button" onClick={startEdit} className="rounded-[4px] px-3.5 py-1.5 text-sm font-semibold" style={{ border: `1px solid ${c.ink}`, color: c.ink, background: "transparent", cursor: "pointer" }}>{t.edit}</button>
                        ) : (
                            <div className="flex items-center gap-2">
                                <button type="button" onClick={save} disabled={saving} className="rounded-[4px] px-3.5 py-1.5 text-sm font-semibold" style={{ background: c.ink, color: c.bg, cursor: saving ? "default" : "pointer", opacity: saving ? 0.6 : 1 }}>{saving ? t.saving : t.save}</button>
                                <button type="button" onClick={cancelEdit} disabled={saving} className="rounded-[4px] px-3.5 py-1.5 text-sm font-semibold" style={{ border: `1px solid ${c.hair}`, color: c.ink70, background: "transparent", cursor: "pointer" }}>{t.cancel}</button>
                            </div>
                        )}
                    </div>
                )}
            </div>
            <div className="my-6 h-px" style={{ background: c.hair }} aria-hidden="true" />

            {notice && <p className="mb-4 text-[0.9rem]" style={{ color: c.red }}>{notice}</p>}

            {state === "loading" && <p style={{ color: c.ink40 }} aria-busy="true">{t.loading}</p>}

            {state === "error" && (
                <div>
                    <p className="text-[1.1rem]" style={{ fontFamily: SERIF, color: c.ink }}>{t.errTitle}</p>
                    <p className="mt-1 text-[0.95rem]" style={{ color: c.ink55 }}>{t.errBody}</p>
                    <button type="button" onClick={load} className="mt-4 rounded-[4px] px-3.5 py-1.5 text-sm font-semibold" style={{ border: `1px solid ${c.ink}`, color: c.ink, background: "transparent", cursor: "pointer" }}>{t.retry}</button>
                </div>
            )}

            {state === "ready" && profile && (
                <>
                    {/* Identity plate */}
                    <div className="rounded-[4px] p-6 sm:p-7" style={{ background: c.panel, border: `1px solid ${c.hair}` }}>
                        {!editing ? (
                            <>
                                <h2 className="text-[1.6rem] font-normal" style={{ fontFamily: SERIF, color: c.ink }}>{profile.name?.trim() || t.none}</h2>
                                <p className="mt-1 text-[0.98rem]" style={{ color: c.ink70 }}>
                                    {[profile.current_role, profile.industries?.[0]].filter(Boolean).join(" · ") || t.none}
                                </p>
                                {(profile.preferred_cities?.length ?? 0) > 0 && (
                                    <Mono style={{ color: c.ink55, marginTop: 8, display: "block" }}>{profile.preferred_cities!.join(" · ")}</Mono>
                                )}
                            </>
                        ) : draft && (
                            <div className="flex flex-col gap-3">
                                <label className="flex flex-col gap-1"><Mono style={{ color: c.ink55 }}>{t.name}</Mono>
                                    <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder={t.namePh} style={inputStyle} /></label>
                                <label className="flex flex-col gap-1"><Mono style={{ color: c.ink55 }}>{t.role}</Mono>
                                    <input value={draft.current_role} onChange={(e) => setDraft({ ...draft, current_role: e.target.value })} placeholder={t.rolePh} style={inputStyle} /></label>
                                <div className="flex flex-col gap-1"><Mono style={{ color: c.ink55 }}>{t.location}</Mono>
                                    <TagEditor c={c} values={draft.preferred_cities} placeholder={t.addCity} onChange={(v) => setDraft({ ...draft, preferred_cities: v })} /></div>
                            </div>
                        )}
                    </div>

                    {/* Skills */}
                    <Section c={c} label={t.skills}>
                        {!editing ? <Chips c={c} values={profile.skills ?? []} empty={t.none} />
                            : draft && <TagEditor c={c} values={draft.skills} placeholder={t.addSkill} onChange={(v) => setDraft({ ...draft, skills: v })} />}
                    </Section>

                    {/* Target roles */}
                    <Section c={c} label={t.targetRoles}>
                        {!editing ? <Chips c={c} values={profile.target_roles ?? []} empty={t.none} />
                            : draft && <TagEditor c={c} values={draft.target_roles} placeholder={t.addRole} onChange={(v) => setDraft({ ...draft, target_roles: v })} />}
                    </Section>

                    {/* Preferences: salary + experience */}
                    <Section c={c} label={t.preferences}>
                        <div className="grid sm:grid-cols-2 gap-4">
                            <div className="rounded-[4px] p-4" style={{ background: c.panel, border: `1px solid ${c.hair}` }}>
                                <Mono style={{ color: c.ink55 }}>{t.salary}</Mono>
                                {!editing ? (
                                    <p className="mt-1 text-[1.1rem]" style={{ fontFamily: SERIF, color: c.ink }}>{profile.salary_expectation_aed != null ? `AED ${profile.salary_expectation_aed.toLocaleString()}` : t.none}</p>
                                ) : draft && (
                                    <input type="number" inputMode="numeric" value={draft.salary_expectation_aed} onChange={(e) => setDraft({ ...draft, salary_expectation_aed: e.target.value })} placeholder="AED" style={{ ...inputStyle, marginTop: 6 }} />
                                )}
                            </div>
                            <div className="rounded-[4px] p-4" style={{ background: c.panel, border: `1px solid ${c.hair}` }}>
                                <Mono style={{ color: c.ink55 }}>{t.experience}</Mono>
                                {!editing ? (
                                    <p className="mt-1 text-[1.1rem]" style={{ fontFamily: SERIF, color: c.ink }}>{profile.years_experience != null ? `${profile.years_experience} ${t.years}` : t.none}</p>
                                ) : draft && (
                                    <input type="number" inputMode="numeric" value={draft.years_experience} onChange={(e) => setDraft({ ...draft, years_experience: e.target.value })} placeholder={t.years} style={{ ...inputStyle, marginTop: 6 }} />
                                )}
                            </div>
                        </div>
                    </Section>
                </>
            )}
        </div>
    );
}
