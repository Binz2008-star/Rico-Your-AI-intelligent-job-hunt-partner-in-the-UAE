'use client';

import React from 'react';
import { TopNav } from '@/components/layout/TopNav';
import { Navigation } from '@/components/layout/Navigation';
import { AuraGlow } from '@/components/ui/AuraGlow';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';

export default function SignalsPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* Atmospheric Background */}
      <AuraGlow variant="magenta" position="top-left" />
      <AuraGlow variant="cyan" position="bottom-right" />

      {/* Top Navigation */}
      <TopNav />

      {/* Main Content */}
      <main className="relative z-10 pt-40 pb-60 px-container-padding-mobile md:px-container-padding-desktop max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-section-gap">
          <h1 className="font-headline-xl text-headline-xl text-on-surface mb-4">Opportunity Signals</h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl">
            Real-time intelligence from recruiter clusters, geographic shifts, and evolving market demand.
          </p>
        </div>

        {/* Signal Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <GlassPanel key={i} className="p-6 rounded-xl border border-white/10 hover:border-primary/30 transition-all group">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <MaterialIcon icon="business" className="text-primary" />
                  </div>
                  <div>
                    <h3 className="font-headline-lg text-headline-lg text-on-surface">Company {i}</h3>
                    <p className="text-on-surface-variant text-sm">London, UK</p>
                  </div>
                </div>
                <span className="text-label-caps text-[10px] px-2 py-1 border border-white/10 rounded">
                  HIGH MATCH
                </span>
              </div>
              <div className="mb-4">
                <p className="text-body-md text-on-surface-variant mb-2">Senior Engineering Role</p>
                <div className="flex gap-2">
                  <span className="text-[10px] text-on-surface-variant/60">Series B</span>
                  <span className="text-[10px] text-on-surface-variant/60">•</span>
                  <span className="text-[10px] text-on-surface-variant/60">Fintech</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-secondary" />
                  <span className="text-label-caps text-[10px] text-secondary">ACTIVE MOMENTUM</span>
                </div>
                <MaterialIcon icon="arrow_forward" className="text-on-surface-variant/40 group-hover:text-primary transition-colors cursor-pointer" />
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
