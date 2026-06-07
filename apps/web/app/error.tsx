"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to error tracking service if one is added later
    console.error("[Rico error boundary]", error);
  }, [error]);

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
          Something went wrong
        </p>
        <h1 className="mb-3 text-2xl font-semibold text-white">
          Unexpected error
        </h1>
        <p className="mb-8 text-sm leading-6 text-text-secondary">
          Rico ran into an unexpected problem. Try again — if the issue persists,
          contact{" "}
          <a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">
            info@ricohunt.com
          </a>
          .
        </p>

        <div className="flex flex-wrap justify-center gap-3">
          <button
            onClick={reset}
            className="inline-flex items-center gap-2 rounded-lg bg-[#f5a623] px-5 py-2.5 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90"
          >
            Try again
          </button>
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-5 py-2.5 text-sm text-white transition-colors hover:bg-white/10"
          >
            Back to home
          </Link>
        </div>
      </div>
    </div>
  );
}
