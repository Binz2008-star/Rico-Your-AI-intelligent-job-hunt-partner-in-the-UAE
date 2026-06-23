"use client";

import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export default function PWAInstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [sparkles, setSparkles] = useState<{ id: number; x: number; y: number; delay: number }[]>([]);

  useEffect(() => {
    // Don't show if already dismissed in this session
    if (sessionStorage.getItem("pwa-prompt-dismissed")) return;

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      // Small delay for a nicer entrance
      setTimeout(() => setVisible(true), 1500);
    };

    window.addEventListener("beforeinstallprompt", handler);

    // Generate sparkle positions once
    setSparkles(
      Array.from({ length: 6 }, (_, i) => ({
        id: i,
        x: 10 + Math.random() * 80,
        y: 10 + Math.random() * 80,
        delay: i * 0.4,
      }))
    );

    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setVisible(false);
    }
    setDeferredPrompt(null);
  };

  const handleDismiss = () => {
    setDismissed(true);
    sessionStorage.setItem("pwa-prompt-dismissed", "1");
    setTimeout(() => setVisible(false), 400);
  };

  if (!visible) return null;

  return (
    <div
      className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 transition-all duration-500 ${
        dismissed ? "opacity-0 translate-y-4" : "opacity-100 translate-y-0"
      }`}
      style={{ maxWidth: "min(380px, calc(100vw - 32px))", width: "100%" }}
    >
      {/* Card */}
      <div
        className="relative overflow-hidden rounded-2xl border border-[#3a2a0f]/60 shadow-2xl"
        style={{
          background: "linear-gradient(135deg, #0d0b06 0%, #1a1408 50%, #0d0b06 100%)",
          boxShadow: "0 0 40px rgba(183,128,20,0.18), 0 20px 60px rgba(0,0,0,0.6)",
        }}
      >
        {/* Animated shimmer border */}
        <div
          className="absolute inset-0 rounded-2xl pointer-events-none"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, rgba(230,180,60,0.12) 40%, rgba(255,210,100,0.22) 50%, rgba(230,180,60,0.12) 60%, transparent 100%)",
            backgroundSize: "200% 100%",
            animation: "shimmer 3s ease-in-out infinite",
          }}
        />

        {/* Sparkles */}
        {sparkles.map((s) => (
          <span
            key={s.id}
            className="absolute pointer-events-none text-xs select-none"
            style={{
              left: `${s.x}%`,
              top: `${s.y}%`,
              animation: `sparkle 2.4s ease-in-out ${s.delay}s infinite`,
              color: "#FFD66D",
              fontSize: "10px",
            }}
          >
            ✦
          </span>
        ))}

        {/* Content */}
        <div className="relative p-4 flex items-center gap-4">
          {/* Icon */}
          <div
            className="flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, #1C1407, #2a1e08)",
              border: "1px solid rgba(183,128,20,0.35)",
              boxShadow: "0 0 16px rgba(183,128,20,0.25)",
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/icons/icon-192.png"
              alt="Rico"
              width={36}
              height={36}
              className="rounded-lg"
            />
          </div>

          {/* Text */}
          <div className="flex-1 min-w-0">
            <p
              className="text-sm font-semibold leading-tight"
              style={{ color: "#F0BD4B" }}
            >
              Install Rico Hunt
            </p>
            <p className="text-xs mt-0.5" style={{ color: "rgba(240,189,75,0.6)" }}>
              Add to your home screen for instant access
            </p>
          </div>

          {/* Dismiss */}
          <button
            onClick={handleDismiss}
            className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center transition-colors"
            style={{ color: "rgba(240,189,75,0.45)" }}
            aria-label="Dismiss"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Install button */}
        <div className="px-4 pb-4">
          <button
            onClick={handleInstall}
            className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 active:scale-95"
            style={{
              background: "linear-gradient(135deg, #B87A16 0%, #E7B84B 50%, #FFD66D 100%)",
              color: "#0d0b06",
              boxShadow: "0 0 20px rgba(183,128,20,0.4), 0 4px 12px rgba(0,0,0,0.3)",
            }}
          >
            Install App ✦
          </button>
        </div>
      </div>

      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% center; }
          100% { background-position: -200% center; }
        }
        @keyframes sparkle {
          0%, 100% { opacity: 0; transform: scale(0.5) rotate(0deg); }
          50% { opacity: 1; transform: scale(1.2) rotate(180deg); }
        }
      `}</style>
    </div>
  );
}
