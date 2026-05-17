"use client";

import Link from "next/link";

export default function LandingPage() {
    return (
        <div className="min-h-screen bg-background flex flex-col relative overflow-hidden">
            {/* Ambient glows - cinematic magenta/cyan */}
            <div className="fixed inset-0 pointer-events-none z-0">
                <div className="absolute -top-[250px] -left-[150px] w-[700px] h-[700px] rounded-full bg-magenta-dim blur-[140px]" />
                <div className="absolute bottom-0 -right-[100px] w-[500px] h-[500px] rounded-full bg-cyan-dim blur-[140px]" />
            </div>

            {/* Top nav */}
            <header className="relative z-10 flex items-center justify-between px-6 py-4 border-b border-border-subtle">
                <Link href="/" className="flex items-center gap-2 text-white font-black text-lg tracking-tight">
                    <div className="w-8 h-8 rounded-[9px] bg-gradient-to-br from-magenta to-cyan flex items-center justify-center text-sm font-black shadow-[0_4px_16px_rgba(255,45,142,0.3)]">R</div>
                    Rico<span className="text-magenta">.ai</span>
                </Link>
                <div className="flex items-center gap-3">
                    <Link href="/login" className="text-[13px] text-text-muted hover:text-white transition-colors">Sign in</Link>
                    <Link href="/signup" className="text-[12px] px-3 py-1.5 rounded-lg bg-magenta text-white hover:bg-magenta-hover transition-colors font-medium">Sign up free</Link>
                </div>
            </header>

            {/* Hero section */}
            <main className="relative z-10 flex-1 flex items-center justify-center px-6">
                <div className="max-w-3xl text-center">
                    <h1 className="text-5xl md:text-6xl font-black text-white mb-6 tracking-tight">
                        Autonomous Career<br />
                        <span className="bg-gradient-duo bg-clip-text text-transparent">Trajectory Intelligence</span>
                    </h1>
                    <p className="text-lg text-text-secondary mb-8 leading-relaxed">
                        Memory-weighted trajectory mapping, command-centered orchestration, and opportunity momentum analysis for autonomous career evolution.
                    </p>
                    <div className="flex flex-col sm:flex-row gap-4 justify-center">
                        <Link href="/signup" className="px-8 py-3 rounded-lg bg-magenta text-white font-semibold hover:bg-magenta-hover transition-colors text-base shadow-[0_4px_16px_rgba(255,45,142,0.28)]">
                            Get started free
                        </Link>
                        <Link href="/upload" className="px-8 py-3 rounded-lg border border-border-soft text-white font-semibold hover:bg-surface-subtle transition-colors text-base">
                            Upload your CV
                        </Link>
                    </div>
                </div>
            </main>
        </div>
    );
}
