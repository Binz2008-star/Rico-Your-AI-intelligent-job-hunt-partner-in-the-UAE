import { DashboardContent } from "@/components/DashboardContent";
import { DashboardShell } from "@/components/DashboardShell";
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
    <DashboardShell>
      <DashboardContent />
    </DashboardShell>
  );
}
