import type { Metadata } from "next";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export const metadata: Metadata = {
  title: "Contact | Rico Hunt",
  description: "Get in touch with the Rico Hunt team. We're based in Dubai and read every message.",
};

export default function ContactPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <AuraGlow aria-hidden="true" variant="magenta" position="top-left" />
      <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" />

      <header className="relative z-10 flex items-center justify-between border-b border-border-subtle bg-black/50 px-5 py-4 backdrop-blur-xl md:px-10">
        <Link href="/" className="flex items-center gap-2 text-lg font-black tracking-tight text-white">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#f5a623] text-[#0a0a1a] text-sm font-black shadow-[0_0_28px_rgba(245,166,35,0.28)]">
            R
          </span>
          <span>
            Rico<span className="text-[#f5a623]"> Hunt</span>
          </span>
        </Link>
        <nav className="flex items-center gap-3">
          <Link href="/about" className="text-sm text-text-secondary transition-colors hover:text-white">
            About
          </Link>
          <Link href="/terms" className="text-sm text-text-secondary transition-colors hover:text-white">
            Terms
          </Link>
          <Link href="/privacy" className="text-sm text-text-secondary transition-colors hover:text-white">
            Privacy
          </Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-16 md:px-10">
        <GlassPanel className="rounded-2xl border border-white/10 p-8 md:p-12">
          <div className="mb-10">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#f5a623]">
              Get in Touch
            </p>
            <h1 className="mb-4 text-3xl font-semibold text-white md:text-4xl">
              We read every message.
            </h1>
            <p className="text-base leading-7 text-text-secondary">
              Whether you have a question about your account, feedback on the product, a business
              enquiry, or something else entirely — reach out and we&apos;ll respond as soon as possible.
            </p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <a
              href="mailto:info@ricohunt.com"
              className="group flex flex-col gap-3 rounded-xl border border-white/10 bg-white/5 p-6 transition-colors hover:bg-white/10"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f5a623]/10 text-[#f5a623]">
                <span className="material-symbols-outlined">mail</span>
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold text-white">Email</p>
                <p className="text-sm text-text-secondary">info@ricohunt.com</p>
                <p className="mt-2 text-xs text-text-tertiary">
                  For general enquiries, support, and business communication.
                  We aim to respond within 24 hours.
                </p>
              </div>
            </a>

            <a
              href="https://wa.me/971585989080?text=Hi%2C%20I%27d%20like%20to%20get%20in%20touch%20with%20Rico%20Hunt"
              target="_blank"
              rel="noopener noreferrer"
              className="group flex flex-col gap-3 rounded-xl border border-white/10 bg-white/5 p-6 transition-colors hover:bg-white/10"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f5a623]/10 text-[#f5a623]">
                <span className="material-symbols-outlined">chat</span>
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold text-white">WhatsApp</p>
                <p className="text-sm text-text-secondary">+971 58 598 9080</p>
                <p className="mt-2 text-xs text-text-tertiary">
                  Quick questions and live support. Available during UAE business hours,
                  Sunday–Thursday.
                </p>
              </div>
            </a>

            <div className="flex flex-col gap-3 rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f5a623]/10 text-[#f5a623]">
                <span className="material-symbols-outlined">location_on</span>
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold text-white">Location</p>
                <p className="text-sm text-text-secondary">Dubai, United Arab Emirates</p>
                <p className="mt-2 text-xs text-text-tertiary">
                  Rico Hunt is a UAE-based platform serving professionals across all Emirates
                  and the wider GCC region.
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-3 rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f5a623]/10 text-[#f5a623]">
                <span className="material-symbols-outlined">schedule</span>
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold text-white">Response Time</p>
                <p className="text-sm text-text-secondary">Within 24 hours</p>
                <p className="mt-2 text-xs text-text-tertiary">
                  We&apos;re a small team that takes support seriously. If you don&apos;t hear back
                  within 24 hours, please resend your message.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-10 rounded-xl border border-[#f5a623]/20 bg-[#f5a623]/5 p-6">
            <h2 className="mb-2 text-base font-semibold text-white">Already using Rico?</h2>
            <p className="mb-4 text-sm text-text-secondary">
              For account-specific help, the fastest path is to message Rico directly inside the app —
              or email us with your registered email address so we can look up your account.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/login"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#f5a623] px-4 py-2 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90"
              >
                Sign in to your account →
              </Link>
              <Link
                href="/chat"
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-white transition-colors hover:bg-white/10"
              >
                Try the public chat
              </Link>
            </div>
          </div>
        </GlassPanel>
      </main>

      <footer className="relative z-10 border-t border-white/10 bg-black/30 px-5 py-8 text-center">
        <div className="mb-3 flex flex-wrap items-center justify-center gap-5">
          <Link href="/about" className="text-xs text-text-tertiary transition-colors hover:text-white">About</Link>
          <span className="text-xs font-medium text-white">Contact</span>
          <Link href="/terms" className="text-xs text-text-tertiary transition-colors hover:text-white">Terms</Link>
          <Link href="/privacy" className="text-xs text-text-tertiary transition-colors hover:text-white">Privacy</Link>
          <Link href="/refund-policy" className="text-xs text-text-tertiary transition-colors hover:text-white">Refunds</Link>
        </div>
        <p className="mb-2 text-xs text-text-tertiary">
          For inquiries, support, and business communication:{" "}
          <a href="mailto:info@ricohunt.com" className="text-[#f5a623] transition-colors hover:opacity-80">
            info@ricohunt.com
          </a>
        </p>
        <p className="text-xs text-text-tertiary">© 2026 Rico Hunt. All rights reserved.</p>
      </footer>
    </div>
  );
}
