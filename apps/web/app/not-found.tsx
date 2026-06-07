import Link from "next/link";

export default function NotFound() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-x-hidden bg-background px-5 text-center">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-40 -top-40 h-96 w-96 rounded-full bg-[#f5a623]/5 blur-3xl" />
        <div className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-[#00d4f0]/5 blur-3xl" />
      </div>

      <div className="relative z-10 max-w-md">
        <div className="mb-6 flex justify-center">
          <Link href="/" className="flex items-center gap-2 text-lg font-black tracking-tight text-white">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f5a623] text-[#0a0a1a] text-sm font-black shadow-[0_0_28px_rgba(245,166,35,0.28)]">
              R
            </span>
            <span>Rico<span className="text-[#f5a623]"> Hunt</span></span>
          </Link>
        </div>

        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#f5a623]">
          404
        </p>
        <h1 className="mb-3 text-2xl font-semibold text-white">
          Page not found
        </h1>
        <p className="mb-8 text-sm leading-6 text-text-secondary">
          The page you are looking for does not exist or has been moved.
        </p>

        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-lg bg-[#f5a623] px-5 py-2.5 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90"
        >
          Back to Rico Hunt
        </Link>
      </div>
    </div>
  );
}
