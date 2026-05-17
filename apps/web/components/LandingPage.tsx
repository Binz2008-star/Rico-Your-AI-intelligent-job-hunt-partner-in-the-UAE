"use client";

import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#06060f] flex flex-col relative overflow-hidden">
      {/* Ambient glows */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute -top-[250px] -left-[150px] w-[700px] h-[700px] rounded-full bg-[rgba(91,79,255,0.06)] blur-[140px]" />
        <div className="absolute bottom-0 -right-[100px] w-[500px] h-[500px] rounded-full bg-[rgba(0,201,167,0.04)] blur-[140px]" />
      </div>

      {/* Top nav */}
      <header className="relative z-10 flex items-center justify-between px-6 py-4 border-b border-white/[0.05]">
        <Link href="/" className="flex items-center gap-2 text-white font-black text-lg tracking-tight">
          <div className="w-8 h-8 rounded-[9px] bg-gradient-to-br from-[#5b4fff] to-[#8b5cf6] flex items-center justify-center text-sm font-black shadow-[0_4px_16px_rgba(91,79,255,0.3)]">R</div>
          Rico<span className="text-[#5b4fff]">.ai</span>
        </Link>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-[13px] text-[#5a5a7a] hover:text-white transition-colors">Sign in</Link>
          <Link href="/signup" className="text-[12px] px-3 py-1.5 rounded-lg bg-[#5b4fff] text-white hover:bg-[#4a3fdf] transition-colors font-medium">Sign up free</Link>
        </div>
      </header>

      {/* Hero section */}
      <main className="relative z-10 flex-1 flex items-center justify-center px-6">
        <div className="max-w-3xl text-center">
          <h1 className="text-5xl md:text-6xl font-black text-white mb-6 tracking-tight">
            Autonomous Career<br />
            <span className="text-[#5b4fff]">Trajectory Intelligence</span>
          </h1>
          <p className="text-lg text-[#8080a0] mb-8 leading-relaxed">
            Memory-weighted trajectory mapping, command-centered orchestration, and opportunity momentum analysis for autonomous career evolution.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/signup" className="px-8 py-3 rounded-lg bg-[#5b4fff] text-white font-semibold hover:bg-[#4a3fdf] transition-colors text-base">
              Get started free
            </Link>
            <Link href="/upload" className="px-8 py-3 rounded-lg border border-white/10 text-white font-semibold hover:bg-white/5 transition-colors text-base">
              Upload your CV
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
