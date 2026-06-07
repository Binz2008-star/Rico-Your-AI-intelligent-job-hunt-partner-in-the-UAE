import { DashboardShell } from "@/components/DashboardShell";
import { DashboardStats } from "@/components/DashboardStats";
import { ProfileSummaryCard } from "@/components/ProfileSummaryCard";
import { SavedSearchesList } from "@/components/SavedSearchesList";
import { StatusCard } from "@/components/StatusCard";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

const RICO_API =
  process.env.BACKEND_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_RICO_API;

async function checkProfileExists(): Promise<boolean | null> {
  if (!RICO_API) return null;
  try {
    const cookieStore = await cookies();
    const cookieHeader = cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ");
    const res = await fetch(`${RICO_API}/api/v1/rico/profile`, {
      headers: { Cookie: cookieHeader },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { profile_exists?: boolean };
    return data.profile_exists ?? false;
  } catch {
    return null;
  }
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ skip?: string }>;
}) {
  const params = await searchParams;
  if (!params.skip) {
    const profileExists = await checkProfileExists();
    if (profileExists === false) {
      redirect("/onboarding");
    }
  }

  return (
    <DashboardShell title="Overview" subtitle="Your career execution progress and next actions">
      <div className="flex flex-col gap-10">
        {/* Career Mission Header */}
        <section>
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
            Career Mission
          </h2>
          <StatusCard title="Career Mission Header" badge="live" href="/command">
            <p className="text-sm text-text-tertiary">
              Rico keeps your search moving across matches, profile readiness, and active applications.
            </p>
            <span
              className="mt-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-2 text-xs font-semibold text-primary transition-all hover:bg-primary/15"
            >
              Open Command Center
            </span>
          </StatusCard>
        </section>

        {/* Job Pipeline Summary */}
        <section>
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
            Job Pipeline
          </h2>
          <DashboardStats />
        </section>

        {/* Next Best Actions */}
        <section>
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
            Next Best Actions
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatusCard title="Search with Rico" badge="live" href="/command">
              <p className="text-sm text-text-tertiary">
                Ask Rico to find matches, prepare an application, or explain what to do next.
              </p>
              <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                Open Command Center
              </span>
            </StatusCard>
            <StatusCard title="Review matches" badge="placeholder" href="/jobs">
              <p className="text-sm text-text-tertiary">
                Check scored opportunities and decide which leads should move into your flow.
              </p>
              <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                View Matches
              </span>
            </StatusCard>
            <StatusCard title="Tune preferences" badge="placeholder" href="/settings">
              <p className="text-sm text-text-tertiary">
                Adjust match thresholds, apply pacing, and alert preferences.
              </p>
              <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                Review Settings
              </span>
            </StatusCard>
          </div>
        </section>

        {/* Profile Readiness */}
        <section>
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
            Profile Readiness
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <ProfileSummaryCard />
            <StatusCard title="Profile gaps" badge="placeholder" href="/profile">
              <p className="text-sm text-text-tertiary">
                Keep your target roles, seniority, locations, and CV details current so Rico can rank jobs accurately.
              </p>
              <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                Update Career Profile
              </span>
            </StatusCard>
          </div>
        </section>

        {/* Application Momentum */}
        <section>
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
            Application Momentum
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <StatusCard title="Application flow" badge="live" href="/flow">
              <p className="text-sm text-text-tertiary">
                Track active applications, interviews, offers, and decisions in one pipeline view.
              </p>
              <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                Open Flow
              </span>
            </StatusCard>
            <StatusCard title="Apply pacing" badge="placeholder" href="/settings">
              <p className="text-sm text-text-tertiary">
                Use your daily apply limit to keep automation controlled and reviewable.
              </p>
              <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                Adjust Pacing
              </span>
            </StatusCard>
          </div>
        </section>

        {/* Rico Activity */}
        <section>
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
            Rico Activity
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <SavedSearchesList />
            <StatusCard title="Saved leads" badge="placeholder" href="/saved-searches">
              <p className="text-sm text-text-tertiary">
                Saved searches and leads help Rico keep future scans aligned with your priorities.
              </p>
              <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                View Saved Leads
              </span>
            </StatusCard>
          </div>
        </section>

      </div>
    </DashboardShell>
  );
}
