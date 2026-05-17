'use client';

import React from 'react';
import { TopNav } from '@/components/layout/TopNav';
import { Navigation } from '@/components/layout/Navigation';
import { AuraGlow } from '@/components/ui/AuraGlow';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import { CommandInput } from '@/components/ui/CommandInput';
import { useOrchestrationStore } from '@/lib/store/useOrchestrationStore';

export default function OrchestratePage() {
  const { executeCommand, isProcessing, currentCommand } = useOrchestrationStore();

  const handleCommandSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const command = formData.get('command') as string;
    if (command) {
      await executeCommand(command);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Atmospheric Background */}
      <AuraGlow variant="magenta" position="top-right" className="animate-pulse-magenta" />
      <AuraGlow variant="cyan" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: '-2s' }} />

      {/* Top Navigation */}
      <TopNav />

      {/* Main Content */}
      <main className="relative z-10 pt-40 pb-60 px-container-padding-mobile md:px-container-padding-desktop max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <h1 className="font-headline-xl text-headline-xl text-on-surface mb-4 tracking-tight">
            How can I assist your{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary animate-pulse-slow">
              next evolution?
            </span>
          </h1>
        </div>

        {/* Command Input */}
        <div className="max-w-4xl mx-auto mb-16">
          <form onSubmit={handleCommandSubmit}>
            <CommandInput name="command" placeholder="Initiate directive..." />
          </form>
        </div>

        {/* Intelligence Fragments */}
        <div className="relative h-[400px]">
          {/* Floating Intelligence Cards */}
          <div className="absolute top-[10%] left-[10%] animate-float">
            <GlassPanel variant="island" className="p-6 rounded-xl border border-white/5 flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse" />
                <span className="text-label-caps text-secondary font-semibold">ROUTING SURFACE</span>
              </div>
              <div className="flex items-end gap-3">
                <span className="font-headline-lg text-headline-lg leading-none">
                  HEALTHY <span className="text-sm font-light opacity-50 tracking-normal">Verified</span>
                </span>
              </div>
              <span className="text-on-surface-variant/60 text-[10px] tracking-widest uppercase">
                VALIDATION PROPAGATION: COMPLETE
              </span>
            </GlassPanel>
          </div>

          <div className="absolute bottom-[20%] right-[10%] animate-float-delayed">
            <GlassPanel variant="island" className="p-6 rounded-xl border border-white/5 flex flex-col gap-2">
              <span className="text-label-caps text-primary font-semibold">IDENTITY FLOW</span>
              <div className="flex items-baseline gap-2">
                <span className="font-headline-lg text-headline-lg leading-none">CORRECTED</span>
                <MaterialIcon icon="verified_user" className="text-primary text-xl animate-pulse" />
              </div>
              <div className="h-[1px] w-full bg-white/10 overflow-hidden mt-1">
                <div className="h-full bg-primary w-3/4 animate-[shimmer_2s_infinite]" />
              </div>
            </GlassPanel>
          </div>

          <div className="absolute top-[30%] right-[20%] animate-float" style={{ animationDelay: '-2s' }}>
            <span className="text-[10px] text-on-surface-variant font-label-caps opacity-40">CV LIFECYCLE</span>
            <GlassPanel variant="island" className="px-4 py-2 rounded-full text-body-md border border-white/5">
              Operational Status: <span className="text-secondary-fixed-dim">Stabilized</span>
            </GlassPanel>
          </div>

          <div className="absolute bottom-[30%] left-[8%] animate-float-delayed">
            <GlassPanel variant="island" className="p-4 rounded-lg border border-white/5">
              <div className="flex items-center gap-3 mb-2">
                <MaterialIcon icon="hub" className="text-on-surface-variant animate-pulse-slow" />
                <span className="text-label-caps text-on-surface-variant">JOB ACTION</span>
              </div>
              <span className="font-headline-lg text-headline-lg text-on-surface">Hardened</span>
            </GlassPanel>
          </div>
        </div>

        {/* Quick Action Cards */}
        <div className="mt-16 flex gap-6 overflow-x-auto w-full justify-center pb-4 no-scrollbar">
          <GlassPanel className="px-6 py-4 rounded-xl border border-white/10 cursor-default hover:bg-white/10 hover:border-secondary/30 transition-all group flex items-center gap-4 shrink-0 animate-float" style={{ animationDelay: '0.2s' }}>
            <MaterialIcon icon="settings_ethernet" className="text-secondary group-hover:rotate-12 transition-transform" />
            <div>
              <p className="text-body-md font-semibold">Router-Level Adapters</p>
              <p className="text-[12px] text-on-surface-variant/60">Stable State Active</p>
            </div>
          </GlassPanel>
          <GlassPanel className="px-6 py-4 rounded-xl border border-white/10 cursor-default hover:bg-white/10 hover:border-primary/30 transition-all group flex items-center gap-4 shrink-0 animate-float" style={{ animationDelay: '0.4s' }}>
            <MaterialIcon icon="account_tree" className="text-primary group-hover:scale-110 transition-transform" />
            <div>
              <p className="text-body-md font-semibold">Orchestration Path</p>
              <p className="text-[12px] text-on-surface-variant/60">Unified Persistence</p>
            </div>
          </GlassPanel>
          <GlassPanel className="px-6 py-4 rounded-xl border border-white/10 cursor-default hover:bg-white/10 hover:border-secondary-fixed-dim/30 transition-all group flex items-center gap-4 shrink-0 animate-float" style={{ animationDelay: '0.6s' }}>
            <MaterialIcon icon="badge" className="text-secondary-fixed-dim group-hover:-translate-y-1 transition-transform" />
            <div>
              <p className="text-body-md font-semibold">Expanded Profile Logic</p>
              <p className="text-[12px] text-on-surface-variant/60">user_id, name, role</p>
            </div>
          </GlassPanel>
        </div>
      </main>

      {/* Bottom Navigation */}
      <Navigation />

      {/* Side Metrics */}
      <aside className="fixed right-container-padding-desktop top-1/2 -translate-y-1/2 flex flex-col gap-12 pointer-events-none hidden lg:flex">
        <div className="opacity-30 flex flex-col items-end animate-pulse-slow">
          <p className="text-label-caps text-secondary">LATENCY</p>
          <p className="font-headline-lg text-headline-lg">12ms</p>
        </div>
        <div className="opacity-30 flex flex-col items-end animate-pulse-slow" style={{ animationDelay: '1s' }}>
          <p className="text-label-caps text-primary">NODES</p>
          <p className="font-headline-lg text-headline-lg">1,402</p>
        </div>
        <div className="opacity-10 flex flex-col items-end">
          <p className="text-[8px] tracking-[0.5em] font-label-caps">SYSTEM_STABLE</p>
        </div>
      </aside>

      {/* Decoration */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
        <div className="absolute inset-0 opacity-[0.04] bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-white/5 to-transparent h-[2px] w-full -top-1 opacity-20 animate-[scanline_10s_linear_infinite]" />
      </div>

      <style jsx>{`
        @keyframes scanline {
          0% { transform: translateY(0vh); }
          100% { transform: translateY(100vh); }
        }
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}
