import { DashboardShell } from "@/components/DashboardShell";
import { StatusCard } from "@/components/StatusCard";

export default function ProfilePage() {
  return (
    <DashboardShell title="Profile">
      <div className="max-w-2xl flex flex-col gap-4">
        <StatusCard title="Profile data" badge="placeholder">
          <p className="text-sm text-zinc-500">
            Profile details will appear here once{" "}
            <code className="text-zinc-400">GET /api/v1/rico/profile</code> is
            exposed to the web client.
          </p>
        </StatusCard>
        <StatusCard title="Preferences" badge="placeholder">
          <p className="text-sm text-zinc-500">
            Job preferences (target roles, salary, cities) will appear here
            once the profile endpoint is connected.
          </p>
        </StatusCard>
      </div>
    </DashboardShell>
  );
}
