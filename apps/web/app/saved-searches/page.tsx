import { DashboardShell } from "@/components/DashboardShell";
import { StatusCard } from "@/components/StatusCard";

export default function SavedSearchesPage() {
  return (
    <DashboardShell title="Saved Searches">
      <div className="max-w-2xl">
        <StatusCard title="Saved searches" badge="placeholder">
          <p className="text-sm text-zinc-500">
            Your saved job searches will appear here once{" "}
            <code className="text-zinc-400">
              GET /api/v1/settings/saved-searches
            </code>{" "}
            is exposed to the web client.
          </p>
        </StatusCard>
      </div>
    </DashboardShell>
  );
}
