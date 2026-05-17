'use client';

import React from 'react';
import { TopNav } from '@/components/layout/TopNav';
import { Navigation } from '@/components/layout/Navigation';
import { AuraGlow } from '@/components/ui/AuraGlow';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';

export default function ArchivePage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* Atmospheric Background */}
      <AuraGlow variant="magenta" position="bottom-left" />
      <AuraGlow variant="cyan" position="top-right" />

      {/* Top Navigation */}
      <TopNav />

      {/* Main Content */}
      <main className="relative z-10 pt-40 pb-60 px-container-padding-mobile md:px-container-padding-desktop max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-section-gap">
          <h1 className="font-headline-xl text-headline-xl text-on-surface mb-4">Memory Archive</h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl">
            Historical trajectory data, learning patterns, and accumulated intelligence from your career evolution.
          </p>
        </div>

        {/* Archive Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[
            { title: '2024 Q1', entries: 12, insight: 'Series B transition pattern' },
            { title: '2024 Q2', entries: 8, insight: 'London fintech cluster alignment' },
            { title: '2024 Q3', entries: 15, insight: 'Engineering leadership trajectory' },
            { title: '2024 Q4', entries: 10, insight: 'Founder-track opportunity mapping' },
          ].map((period, i) => (
            <GlassPanel key={i} className="p-6 rounded-xl border border-white/10 hover:border-primary/30 transition-all group">
              <div className="flex items-start justify-between mb-4">
                <h3 className="font-headline-lg text-headline-lg text-on-surface">{period.title}</h3>
                <MaterialIcon icon="history" className="text-on-surface-variant/40 group-hover:text-primary transition-colors" />
              </div>
              <div className="mb-4">
                <p className="text-body-md text-on-surface-variant mb-2">{period.entries} trajectory points</p>
                <p className="text-[12px] text-on-surface-variant/60 italic">{period.insight}</p>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                <span className="text-label-caps text-[10px] text-primary">MEMORY INTEGRATED</span>
              </div>
            </GlassPanel>
          ))}
        </div>
      </main>

      {/* Bottom Navigation */}
      <Navigation />

      {/* Decoration */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
        <div className="absolute inset-0 opacity-[0.04] bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />
      </div>
    </div>
  );
}
