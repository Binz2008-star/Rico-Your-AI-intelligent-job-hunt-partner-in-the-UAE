"use client";

import { DashboardShell } from "@/components/DashboardShell";
import { StatusCard } from "@/components/StatusCard";
import { fetchSavedSearches, type SavedSearch } from "@/lib/api";
import { useEffect, useState } from "react";

export default function SavedSearchesPage() {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSavedSearches()
      .then((r) => setSearches(r.searches))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardShell title="Saved Searches">
      <div className="max-w-2xl">
        {loading && (
          <StatusCard title="Saved searches" badge="pending">
            <p className="text-sm text-[#5a5a7a]">Loading…</p>
          </StatusCard>
        )}

        {!loading && error && (
          <StatusCard title="Saved searches" badge="error">
            <p className="text-sm text-[#5a5a7a]">
              Could not load saved searches. Make sure you are signed in.
            </p>
          </StatusCard>
        )}

        {!loading && !error && searches.length === 0 && (
          <StatusCard title="Saved searches" badge="live" value="0">
            <p className="text-sm text-[#5a5a7a]">
              No saved searches yet. Use the Rico chat to save a job search.
            </p>
          </StatusCard>
        )}

        {!loading && !error && searches.length > 0 && (
          <StatusCard
            title="Saved searches"
            badge="live"
            value={String(searches.length)}
          >
            <ul className="mt-1 flex flex-col gap-2">
              {searches.map((s) => (
                <li
                  key={s.id}
                  className="flex items-start justify-between gap-3 rounded-lg bg-[rgba(255,255,255,0.03)] px-3 py-2.5"
                >
                  <span className="text-sm text-[#eeeef5] break-all">
                    {s.query}
                  </span>
                  <span className="shrink-0 text-xs text-[#5a5a7a] mt-0.5">
                    {new Date(s.created_at).toLocaleDateString()}
                  </span>
                </li>
              ))}
            </ul>
          </StatusCard>
        )}
      </div>
    </DashboardShell>
  );
}
