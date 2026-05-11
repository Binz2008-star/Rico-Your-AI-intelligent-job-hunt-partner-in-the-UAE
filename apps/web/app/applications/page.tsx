"use client";

import { DashboardShell } from "@/components/DashboardShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ToastContainer } from "@/components/ui/Toast";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import {
  ApiError,
  getApplications,
  updateApplicationStatus,
} from "@/lib/api";
import type { Application, ApplicationStatus } from "@/types";
import { useEffect, useState } from "react";

const STATUS_OPTIONS: ApplicationStatus[] = [
  "applied",
  "interview",
  "offer",
  "rejected",
  "saved",
  "opened",
  "decision_made",
];

function fmtDate(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export default function ApplicationsPage() {
  const { user } = useAuth();
  const { toasts, toast } = useToast();
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<"auth" | "other" | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    setError(null);
    getApplications()
      .then((r) => setApps(r.applications))
      .catch((err) => {
        const is401 = err instanceof ApiError && err.statusCode === 401;
        setError(is401 ? "auth" : "other");
        toast(is401 ? "Session expired — please log in again" : "Could not load applications", "error");
      })
      .finally(() => setLoading(false));
  }, [user, toast]);

  const changeStatus = async (app: Application, status: ApplicationStatus) => {
    if (!user || updating) return;
    setUpdating(app.application_id);
    try {
      await updateApplicationStatus(app.job_id, { status });
      setApps((prev) => prev.map((a) => (a.job_id === app.job_id ? { ...a, status } : a)));
      toast("Status updated", "success");
    } catch {
      toast("Update failed", "error");
    } finally {
      setUpdating(null);
    }
  };

  const grouped = STATUS_OPTIONS.reduce<Record<ApplicationStatus, Application[]>>(
    (acc, s) => ({ ...acc, [s]: apps.filter((a) => a.status === s) }),
    {} as Record<ApplicationStatus, Application[]>
  );

  const statLabels: Record<ApplicationStatus, string> = {
    applied: "Applied",
    interview: "Interview",
    offer: "Offer",
    rejected: "Rejected",
    saved: "Saved",
    opened: "Opened",
    decision_made: "Decision",
  };

  return (
    <DashboardShell>
      <div className="px-8 py-6 border-b border-white/5 bg-[rgba(7,7,18,0.7)] backdrop-blur-md sticky top-0 z-10">
        <h1 className="font-['Cabinet_Grotesk',sans-serif] font-black text-[22px] tracking-tight">Applications</h1>
        <p className="text-[13px] text-[#5a5a7a] mt-0.5">
          {loading ? "Loading…" : `${apps.length} tracked across all stages`}
        </p>
      </div>

      <div className="p-8 flex flex-col gap-6">
        {/* summary strip */}
        {!loading && !error && (
          <div className="grid grid-cols-2 md:grid-cols-7 gap-3">
            {STATUS_OPTIONS.map((s) => (
              <div key={s} className="bg-[#13132a]/80 border border-[rgba(255,255,255,0.06)] rounded-xl p-4 text-center">
                <p className="font-['Cabinet_Grotesk',sans-serif] font-black text-[28px] tracking-tight text-[#eeeef5]">
                  {grouped[s].length}
                </p>
                <p className="text-[10px] text-[#5a5a7a] mt-1 uppercase tracking-wider">{statLabels[s]}</p>
              </div>
            ))}
          </div>
        )}

        {/* table */}
        <div className="bg-[#13132a]/80 border border-[rgba(255,255,255,0.06)] rounded-2xl overflow-hidden">
          {loading ? (
            <div className="flex flex-col">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-16 border-b border-[rgba(255,255,255,0.04)] bg-[rgba(255,255,255,0.015)] animate-pulse" />
              ))}
            </div>
          ) : error === "auth" ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
              <span className="text-4xl opacity-25">🔒</span>
              <p className="text-[14px] text-[#5a5a7a]">Session expired</p>
              <a
                href="/login"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[rgba(91,79,255,0.15)] text-[#a78bfa] border border-[rgba(91,79,255,0.25)] text-[13px] font-semibold hover:bg-[rgba(91,79,255,0.25)] transition-all"
              >
                Log in again
              </a>
            </div>
          ) : error === "other" ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
              <span className="text-4xl opacity-25">⚠️</span>
              <p className="text-[14px] text-[#5a5a7a]">Could not load applications</p>
              <p className="text-[12px] text-[#5a5a7a]">The backend may be unavailable. Please try again.</p>
            </div>
          ) : apps.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
              <span className="text-4xl opacity-25">📄</span>
              <p className="text-[14px] text-[#5a5a7a]">No applications tracked yet</p>
              <p className="text-[12px] text-[#5a5a7a]">Apply to jobs from the Jobs page and they&apos;ll appear here</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <div className="min-w-[760px]">
                {/* header row */}
                <div className="grid grid-cols-[2fr_1.5fr_1fr_1fr_1fr] gap-4 px-5 py-3 border-b border-white/5">
                  {["Role", "Company", "Applied", "Status", "Action"].map((h) => (
                    <span key={h} className="text-[10px] uppercase tracking-wider text-[#5a5a7a] font-semibold">
                      {h}
                    </span>
                  ))}
                </div>
                {apps.map((app, i) => (
                  <div
                    key={app.application_id}
                    className={`grid grid-cols-[2fr_1.5fr_1fr_1fr_1fr] gap-4 px-5 py-4 items-center transition-colors hover:bg-[rgba(255,255,255,0.015)] ${i < apps.length - 1 ? "border-b border-[rgba(255,255,255,0.04)]" : ""
                      }`}
                  >
                    <div className="min-w-0">
                      <p className="text-[13px] font-medium text-[#eeeef5] truncate">{app.title}</p>
                      {app.apply_url && app.apply_url !== "#" && (
                        <a href={app.apply_url} target="_blank" rel="noreferrer" className="text-[11px] text-[#a78bfa] hover:text-[#eeeef5]">
                          View listing ↗
                        </a>
                      )}
                    </div>
                    <p className="text-[13px] text-[#8080a0] truncate">{app.company}</p>
                    <p className="text-[12px] text-[#5a5a7a]">{fmtDate(app.applied_at)}</p>
                    <StatusBadge status={app.status} />
                    <select
                      value={app.status}
                      onChange={(e) => changeStatus(app, e.target.value as ApplicationStatus)}
                      disabled={updating === app.application_id}
                      aria-label={`Change status for ${app.title}`}
                      className="bg-[#0d0d1f] border border-[rgba(255,255,255,0.08)] rounded-lg px-2 py-1.5 text-[11px] text-[#8080a0] outline-none focus:border-[rgba(91,79,255,0.4)] cursor-pointer disabled:opacity-40"
                    >
                      {STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s}>{statLabels[s]}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
      <ToastContainer toasts={toasts} />
    </DashboardShell>
  );
}
