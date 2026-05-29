"use client";

import { fetchMe, requestJson } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

interface SignupRecord {
    id: number;
    email: string;
    role: string;
    created_at: string | null;
    last_login_at: string | null;
}

interface IntentRecord {
    id: number;
    user_id: string | null;
    email: string | null;
    plan: string;
    billing_mode: string;
    source_page: string;
    created_at: string;
}

function fmt(iso: string | null) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString("en-AE", {
        day: "numeric", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
    });
}

function waLink(email: string | null, plan?: string) {
    const text = email
        ? `Hi, I'm following up with ${email}${plan ? ` who showed interest in the ${plan} plan` : ""} on Rico Hunt.`
        : `Hi, following up on a Rico Hunt upgrade interest${plan ? ` for the ${plan} plan` : ""}.`;
    return `https://wa.me/?text=${encodeURIComponent(text)}`;
}

export default function AdminLeadsPage() {
    const router = useRouter();
    const [signups, setSignups] = useState<SignupRecord[]>([]);
    const [intents, setIntents] = useState<IntentRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [usersRes, intentsRes] = await Promise.all([
                requestJson<SignupRecord[]>("/api/v1/admin/subscriptions/users"),
                requestJson<IntentRecord[]>("/api/v1/admin/subscriptions/intents"),
            ]);
            setSignups(usersRes);
            setIntents(intentsRes);
        } catch {
            setError("Could not load data. Make sure you are signed in as admin.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchMe().then((me) => {
            if (!me.authenticated) { router.replace("/login"); return; }
            if (me.role !== "admin") { router.replace("/dashboard"); return; }
            void load();
        }).catch(() => router.replace("/login"));
    }, [router, load]);

    if (loading) {
        return (
            <div className="min-h-screen bg-[#080818] flex items-center justify-center">
                <div className="w-5 h-5 rounded-full border-2 border-[#f5a623] border-t-transparent animate-spin" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#080818] text-white px-5 py-8 md:px-10">
            {/* Header */}
            <div className="mb-8 flex items-center justify-between gap-4">
                <div>
                    <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-[#f5a623]">Admin</p>
                    <h1 className="mt-1 text-2xl font-bold text-white">Leads & Signups</h1>
                </div>
                <button
                    onClick={load}
                    className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/70 hover:text-white hover:bg-white/10 transition-colors"
                >
                    Refresh
                </button>
            </div>

            {error && (
                <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300">
                    {error}
                </div>
            )}

            {/* Summary cards */}
            <div className="mb-8 grid gap-4 sm:grid-cols-3">
                <div className="rounded-xl border border-white/[0.06] bg-[#0f0f22] px-5 py-4">
                    <p className="text-[11px] font-mono uppercase tracking-widest text-white/40">Total signups</p>
                    <p className="mt-2 text-3xl font-bold text-white">{signups.length}</p>
                </div>
                <div className="rounded-xl border border-white/[0.06] bg-[#0f0f22] px-5 py-4">
                    <p className="text-[11px] font-mono uppercase tracking-widest text-white/40">Upgrade intents</p>
                    <p className="mt-2 text-3xl font-bold text-[#f5a623]">{intents.length}</p>
                </div>
                <div className="rounded-xl border border-white/[0.06] bg-[#0f0f22] px-5 py-4">
                    <p className="text-[11px] font-mono uppercase tracking-widest text-white/40">Pro intents</p>
                    <p className="mt-2 text-3xl font-bold text-[#00e5ff]">
                        {intents.filter(i => i.plan === "pro").length}
                    </p>
                </div>
            </div>

            {/* Upgrade intents */}
            <section className="mb-10">
                <h2 className="mb-4 text-base font-semibold text-white">
                    Upgrade intents
                    <span className="ml-2 text-sm font-normal text-white/40">— who clicked Upgrade</span>
                </h2>
                {intents.length === 0 ? (
                    <p className="text-sm text-white/30">No intents recorded yet.</p>
                ) : (
                    <div className="overflow-x-auto rounded-xl border border-white/[0.06]">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                                    <th className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-widest text-white/30">Email / User</th>
                                    <th className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-widest text-white/30">Plan</th>
                                    <th className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-widest text-white/30">Mode</th>
                                    <th className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-widest text-white/30">Time</th>
                                    <th className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-widest text-white/30">Follow up</th>
                                </tr>
                            </thead>
                            <tbody>
                                {intents.map((intent) => (
                                    <tr key={intent.id} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                                        <td className="px-4 py-3 text-white/80">
                                            {intent.email ?? intent.user_id ?? <span className="text-white/25">anonymous</span>}
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide ${
                                                intent.plan === "premium"
                                                    ? "bg-[rgba(91,79,255,0.15)] text-[#7b6fff]"
                                                    : "bg-[rgba(245,166,35,0.15)] text-[#f5a623]"
                                            }`}>
                                                {intent.plan}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-white/40 text-xs">{intent.billing_mode}</td>
                                        <td className="px-4 py-3 text-white/40 text-xs">{fmt(intent.created_at)}</td>
                                        <td className="px-4 py-3">
                                            <a
                                                href={waLink(intent.email ?? intent.user_id, intent.plan)}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center gap-1.5 rounded-lg bg-[rgba(37,211,102,0.1)] px-3 py-1.5 text-[12px] font-semibold text-[#25d366] hover:bg-[rgba(37,211,102,0.18)] transition-colors"
                                            >
                                                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                                                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                                                </svg>
                                                WhatsApp
                                            </a>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>

            {/* Recent signups */}
            <section>
                <h2 className="mb-4 text-base font-semibold text-white">
                    Recent signups
                    <span className="ml-2 text-sm font-normal text-white/40">— all registered users</span>
                </h2>
                {signups.length === 0 ? (
                    <p className="text-sm text-white/30">No users found.</p>
                ) : (
                    <div className="overflow-x-auto rounded-xl border border-white/[0.06]">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                                    <th className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-widest text-white/30">Email</th>
                                    <th className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-widest text-white/30">Role</th>
                                    <th className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-widest text-white/30">Signed up</th>
                                    <th className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-widest text-white/30">Last login</th>
                                    <th className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-widest text-white/30">Follow up</th>
                                </tr>
                            </thead>
                            <tbody>
                                {signups.map((u) => (
                                    <tr key={u.id} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                                        <td className="px-4 py-3 text-white/80">{u.email}</td>
                                        <td className="px-4 py-3">
                                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide ${
                                                u.role === "admin"
                                                    ? "bg-red-500/10 text-red-400"
                                                    : "bg-white/[0.06] text-white/40"
                                            }`}>
                                                {u.role}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-white/40 text-xs">{fmt(u.created_at)}</td>
                                        <td className="px-4 py-3 text-white/40 text-xs">{fmt(u.last_login_at)}</td>
                                        <td className="px-4 py-3">
                                            <a
                                                href={waLink(u.email)}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center gap-1.5 rounded-lg bg-[rgba(37,211,102,0.1)] px-3 py-1.5 text-[12px] font-semibold text-[#25d366] hover:bg-[rgba(37,211,102,0.18)] transition-colors"
                                            >
                                                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                                                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                                                </svg>
                                                WhatsApp
                                            </a>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>
        </div>
    );
}
