"use client";

import { StatusCard } from "@/components/StatusCard";
import { deleteSavedSearch, fetchSavedSearches, type SavedSearch } from "@/lib/api";
import { useEffect, useState } from "react";

export function SavedSearchesList() {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [error, setError] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const handleDelete = async (id: string, query: string) => {
    if (!confirm(`Delete saved search: "${query}"?`)) {
      return;
    }

    setDeleteError(null);
    try {
      await deleteSavedSearch(id);
      // Remove the deleted item from local state
      setSearches((current) => current.filter((s) => s.id !== id));
    } catch (err) {
      setDeleteError("Failed to delete saved search");
    }
  };

  useEffect(() => {
    fetchSavedSearches()
      .then((r) => setSearches(r.searches))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <StatusCard title="Saved searches" badge="pending">
        <p className="text-sm text-on-surface-variant">Loading…</p>
      </StatusCard>
    );
  }

  if (error) {
    return (
      <StatusCard title="Saved searches" badge="error">
        <p className="text-sm text-on-surface-variant">Could not load saved searches.</p>
      </StatusCard>
    );
  }

  if (searches.length === 0) {
    return (
      <StatusCard title="Saved searches" badge="live" value="0">
        <p className="text-sm text-on-surface-variant">
          No saved searches yet. Use the Rico chat to save a job search.
        </p>
      </StatusCard>
    );
  }

  return (
    <StatusCard title="Saved searches" badge="live" value={String(searches.length)}>
      {deleteError && (
        <p className="mb-2 text-sm text-red-400">{deleteError}</p>
      )}
      <ul className="mt-1 flex flex-col gap-2">
        {searches.map((s) => (
          <li
            key={s.id}
            className="flex items-start justify-between gap-2 rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2.5 text-sm"
          >
            <span className="flex-1 break-all text-on-surface">{s.query}</span>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-on-surface-variant/70">
                {new Date(s.created_at).toLocaleDateString()}
              </span>
              <button
                onClick={() => handleDelete(s.id, s.query)}
                className="text-xs text-red-400 hover:text-red-300 transition-colors"
                title="Delete saved search"
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </StatusCard>
  );
}
