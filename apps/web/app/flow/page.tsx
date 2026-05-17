'use client';

import React from 'react';
import { TopNav } from '@/components/layout/TopNav';
import { Navigation } from '@/components/layout/Navigation';
import { AuraGlow } from '@/components/ui/AuraGlow';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';

export default function FlowPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* Atmospheric Background */}
      <AuraGlow variant="cyan" position="top-left" />
      <AuraGlow variant="magenta" position="bottom-right" />

      {/* Top Navigation */}
      <TopNav />

      {/* Main Content */}
      <main className="relative z-10 pt-40 pb-60 px-container-padding-mobile md:px-container-padding-desktop max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-section-gap">
          <h1 className="font-headline-xl text-headline-xl text-on-surface mb-4">Application Flow</h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl">
            Track your application pipeline with temporal orchestration and memory-weighted intelligence.
          </p>
        </div>

        {/* Flow Timeline */}
        <div className="space-y-8">
          {[
            { stage: 'Applied', company: 'TechCorp London', role: 'Senior Engineer', status: 'In Review' },
            { stage: 'Screening', company: 'FinanceHub', role: 'Tech Lead', status: 'Scheduled' },
            { stage: 'Interview', company: 'DataFlow', role: 'Engineering Manager', status: 'Completed' },
          ].map((item, i) => (
            <GlassPanel key={i} className="p-8 rounded-xl border border-white/10 hover:border-primary/30 transition-all">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-surface-container flex items-center justify-center">
                    <span className="font-headline-lg text-headline-lg text-primary">{i + 1}</span>
                  </div>
                  <div>
                    <h3 className="font-headline-lg text-headline-lg text-on-surface">{item.company}</h3>
                    <p className="text-on-surface-variant">{item.role}</p>
                  </div>
                </div>
                <span className="text-label-caps text-[10px] px-3 py-1 border border-white/10 rounded-full">
                  {item.stage}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-full h-[1px] bg-white/10" />
                <span className="text-label-caps text-[10px] text-secondary">{item.status}</span>
                <MaterialIcon icon="check_circle" className="text-secondary text-sm" />
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
