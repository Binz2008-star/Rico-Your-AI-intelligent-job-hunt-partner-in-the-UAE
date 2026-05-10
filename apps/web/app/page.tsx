import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 px-4 text-center">
      <div className="max-w-2xl">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs text-indigo-400">
          Now in early access
        </div>

        <h1 className="mb-4 text-4xl font-bold tracking-tight text-white sm:text-5xl md:text-6xl">
          Your autonomous AI job hunter.
        </h1>

        <p className="mb-8 text-lg leading-relaxed text-zinc-400">
          Rico AI finds matching jobs, explains why they fit, tracks
          applications, and helps you apply faster.
        </p>

        <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/login"
            className="rounded-lg bg-indigo-600 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-indigo-500"
          >
            Sign in
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg border border-zinc-700 px-6 py-3 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500 hover:text-white"
          >
            View dashboard
          </Link>
        </div>

        <p className="mt-12 text-xs text-zinc-600">
          Powered by Rico AI — backend at{" "}
          <span className="text-zinc-500">rico-job-automation-api.onrender.com</span>
        </p>
      </div>
    </main>
  );
}
