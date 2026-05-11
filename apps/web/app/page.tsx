"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

/* ─── Icons ─── */
function LightningIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  );
}

function ArrowRightIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M5 12h14M12 5l7 7-7 7" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

/* ─── Ambient glows ─── */
function AmbientGlows() {
  return (
    <>
      <div className="fixed w-[700px] h-[700px] rounded-full blur-[140px] pointer-events-none z-0 opacity-0 animate-[ambIn_1.5s_ease_.2s_forwards] bg-[rgba(91,79,255,0.09)] -top-[250px] -left-[150px]" />
      <div className="fixed w-[500px] h-[500px] rounded-full blur-[140px] pointer-events-none z-0 opacity-0 animate-[ambIn_1.5s_ease_.5s_forwards] bg-[rgba(0,201,167,0.06)] bottom-0 -right-[100px]" />
      <div className="fixed w-[350px] h-[350px] rounded-full blur-[140px] pointer-events-none z-0 opacity-0 animate-[ambIn_1.5s_ease_.8s_forwards] bg-[rgba(245,166,35,0.04)] top-[45%] left-[40%]" />
      <style jsx>{`
        @keyframes ambIn { to { opacity: 1 } }
      `}</style>
    </>
  );
}

/* ─── Grid lines background ─── */
function GridLines() {
  return (
    <>
      <div className="grid-lines absolute inset-0 pointer-events-none" />
      <style jsx>{`
        .grid-lines {
          background-image:
            linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px);
          background-size: 64px 64px;
          mask-image: radial-gradient(ellipse 75% 70% at 50% 40%, black 30%, transparent 100%);
          -webkit-mask-image: radial-gradient(ellipse 75% 70% at 50% 40%, black 30%, transparent 100%);
        }
      `}</style>
    </>
  );
}

/* ─── Reveal on scroll hook ─── */
function useReveal() {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) setVisible(true); }),
      { threshold: 0.12 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return { ref, visible };
}

function Reveal({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const { ref, visible } = useReveal();
  return (
    <div
      ref={ref}
      className={`transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"} ${className}`}
    >
      {children}
    </div>
  );
}

/* ─── Data ─── */
const TECH_PILLS = [
  { emoji: "🤖", label: "OpenAI GPT-4.1" },
  { emoji: "⚡", label: "FastAPI" },
  { emoji: "🗄️", label: "Neon PostgreSQL" },
  { emoji: "📬", label: "Telegram Bot API" },
  { emoji: "📋", label: "Jotform Webhooks" },
  { emoji: "🔍", label: "JobSpy UAE" },
];

const FLOW_STEPS = [
  { num: "1", icon: "📋", title: "Quick Start Form", desc: "Tell Rico your name, Telegram handle, dream role, and preferred UAE city. 60 seconds — that's it." },
  { num: "2", icon: "🧠", title: "Rico Learns You", desc: "Rico parses your CV and learns your preferences through chat, building your intelligent career profile progressively." },
  { num: "3", icon: "🔍", title: "Background Scanning", desc: "Rico runs the full UAE job pipeline daily — fetching, filtering, scoring — while you live your life. No manual searching." },
  { num: "4", icon: "📊", title: "Scored & Explained", desc: "Every match gets a fit score with a plain reason: title match, salary fit, skill overlap. You see why, not just that it ranked." },
  { num: "5", icon: "✅", title: "You Approve, Rico Acts", desc: "Save, ignore, or apply via Telegram with one tap. Rico tracks everything and sends follow-up reminders automatically." },
];

const FEATURES = [
  { icon: "🎯", title: "AI Job Matching", desc: "Rico scans UAE job boards daily via JobSpy and scores every role for title fit, salary range, skills overlap, and seniority — with clear reasoning for each result.", endpoint: "GET /api/v1/jobs" },
  { icon: "💬", title: "Conversational AI", desc: "Chat with Rico in English, Arabic, or mixed language. Ask \"find HSE Manager jobs in Dubai\" and get intelligent, real-time answers powered by OpenAI GPT-4.1 tool-calling.", endpoint: "POST /api/v1/rico/chat" },
  { icon: "📄", title: "CV Parsing", desc: "Upload your CV once. Rico extracts skills, experience, and career signals automatically using the built-in CV parser, then learns more with every conversation.", endpoint: "POST /api/v1/rico/profile", note: "Planned" },
  { icon: "✈️", title: "Telegram-First Alerts", desc: "Rico delivers job cards to Telegram with one-tap Save / Ignore / Apply inline buttons. Your daily habit loop for staying on top of opportunities without the noise.", endpoint: "POST /api/telegram/webhook" },
  { icon: "📈", title: "Application Tracking", desc: "Every application, follow-up, and outcome tracked in one place via Neon PostgreSQL. Rico reminds you when to follow up and learns from every outcome.", endpoint: "GET /api/v1/applications" },
  { icon: "🛡️", title: "Safety-First by Design", desc: "Rico never applies without your explicit approval. Built-in safety and quality layers prevent fake experience, forged documents, or recruiter spam. You stay in control, always.", endpoint: "Safety Layer · Always On" },
];

const ENDPOINTS = [
  { method: "GET", path: "/health", desc: "Server health check — env readiness, DB, Rico identity validation", tag: "Public" },
  { method: "GET", path: "/api/v1/jobs", desc: "Scored & ranked job matches with fit explanation per role", tag: "JobSpy · Scoring Engine" },
  { method: "GET", path: "/api/v1/applications", desc: "Track all your applications, statuses, and outcomes", tag: "Neon DB" },
  { method: "GET", path: "/api/v1/settings", desc: "Read your job matching preferences and thresholds", tag: "Neon DB" },
  { method: "GET", path: "/api/v1/rico/profile", desc: "Read your career profile, preferences, and learning signals", tag: "Neon DB" },
  { method: "POST", path: "/api/v1/rico/chat", desc: "Conversational interface — English, Arabic, mixed language via NLU + OpenAI agent", tag: "OpenAI Tool-Calling" },
];

const INTEGRATIONS = [
  { icon: "🤖", name: "OpenAI", role: "GPT-4.1 Mini · Tool-calling agent brain", status: "live" },
  { icon: "✈️", name: "Telegram", role: "Primary habit loop · Job alerts & chat", status: "live" },
  { icon: "📋", name: "Jotform", role: "Quick Start onboarding · Webhook-powered", status: "live" },
  { icon: "🗄️", name: "Neon DB", role: "PostgreSQL · Users, profiles, applications", status: "live" },
  { icon: "📧", name: "Gmail", role: "Application sync · Follow-up tracking", status: "planned" },
  { icon: "🔍", name: "JobSpy", role: "UAE multi-board job scraping pipeline", status: "live" },
  { icon: "⚡", name: "Redis", role: "Background workers · Async job queues", status: "live" },
  { icon: "🔒", name: "Safety Layer", role: "Guardrails · Approval gates · Privacy", status: "live" },
];

const SAFETY_ALWAYS = [
  "Stays honest and transparent about every match",
  "Asks before taking any high-impact action",
  "Protects your personal data and CV",
  "Lets you change preferences or opt out anytime",
  "Explains rejections constructively",
  "Supports English, Arabic, and mixed language",
  "Keeps you in full control of every application",
];

const SAFETY_NEVER = [
  "Applies to a job without your explicit approval",
  "Fakes your experience or forges documents",
  "Lies on your behalf to recruiters",
  "Shares your personal data without permission",
  "Spams recruiters or submits bulk applications",
  "Discriminates using protected traits",
  "Creates false hope or manipulates your expectations",
];

/* ─── Mockup job card ─── */
function MockJob({ ico, color, title, company, tags, score, scoreColor }: {
  ico: string; color: string; title: string; company: string; tags: string[]; score: string; scoreColor: string;
}) {
  return (
    <div className="bg-[rgba(255,255,255,0.025)] border border-[rgba(255,255,255,0.06)] rounded-[10px] p-3 flex gap-3 items-start hover:border-[rgba(91,79,255,0.3)] hover:bg-[rgba(91,79,255,0.04)] transition-all">
      <div className={`w-[34px] h-[34px] rounded-lg flex items-center justify-center font-['Cabinet_Grotesk',sans-serif] font-black text-[11px] shrink-0 ${color}`}>{ico}</div>
      <div className="flex-1 min-w-0">
        <div className="text-[12px] font-semibold text-[#eeeef5] truncate">{title}</div>
        <div className="text-[11px] text-[#5a5a7a] mt-0.5">{company}</div>
        <div className="flex gap-1 mt-1.5 flex-wrap">
          {tags.map((t) => (
            <span key={t} className="text-[9px] px-[7px] py-[2px] rounded bg-[rgba(255,255,255,0.04)] text-[#5a5a7a] border border-[rgba(255,255,255,0.06)]">{t}</span>
          ))}
        </div>
      </div>
      <div className={`font-['Cabinet_Grotesk',sans-serif] font-black text-[13px] px-[9px] py-[3px] rounded-full shrink-0 self-start ${scoreColor}`}>{score}</div>
    </div>
  );
}

/* ─── Main page ─── */
export default function HomePage() {
  const [navStuck, setNavStuck] = useState(false);

  useEffect(() => {
    const onScroll = () => setNavStuck(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="relative">
      <AmbientGlows />

      {/* Nav */}
      <nav className={`fixed top-0 left-0 right-0 z-[200] px-6 md:px-12 py-5 flex items-center justify-between transition-all duration-300 ${navStuck ? "bg-[rgba(6,6,15,0.88)] backdrop-blur-2xl border-b border-[rgba(255,255,255,0.06)] py-3.5" : ""}`}>
        <Link href="/" className="flex items-center gap-2.5 font-['Cabinet_Grotesk',sans-serif] font-black text-[20px] text-[#eeeef5] tracking-tight no-underline">
          <div className="w-8 h-8 rounded-[9px] bg-gradient-to-br from-[#5b4fff] to-[#8b5cf6] flex items-center justify-center text-[15px] font-black text-white shadow-[0_4px_16px_rgba(91,79,255,0.3)]">R</div>
          Rico AI
        </Link>
        <div className="flex items-center gap-6">
          <a href="#how" className="hidden md:block text-[14px] text-[#8080a0] font-medium no-underline hover:text-[#eeeef5] transition-colors">How it works</a>
          <a href="#features" className="hidden md:block text-[14px] text-[#8080a0] font-medium no-underline hover:text-[#eeeef5] transition-colors">Features</a>
          <a href="#api" className="hidden md:block text-[14px] text-[#8080a0] font-medium no-underline hover:text-[#eeeef5] transition-colors">API</a>
          <Link href="/login" className="text-[14px] text-[#8080a0] font-medium no-underline hover:text-[#eeeef5] transition-colors">Log in</Link>
          <Link href="/dashboard" className="hidden sm:inline-flex items-center bg-[#5b4fff] text-white px-5 py-2 rounded-lg text-[14px] font-semibold no-underline transition-all hover:translate-y-[-1px] shadow-[0_4px_16px_rgba(91,79,255,0.3)] hover:shadow-[0_8px_28px_rgba(91,79,255,0.3)]">Dashboard →</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-[1] min-h-screen flex flex-col items-center justify-center text-center px-6 pt-36 pb-20 overflow-hidden">
        <GridLines />

        <div className="relative z-[1]">
          <div className="inline-flex items-center gap-2 bg-[rgba(0,201,167,0.08)] border border-[rgba(0,201,167,0.2)] rounded-full px-[14px] py-[5px] text-[12px] text-[#00c9a7] font-semibold tracking-wider uppercase mb-7">
            <span className="w-[6px] h-[6px] bg-[#00c9a7] rounded-full shadow-[0_0_10px_#00c9a7] animate-[blink_2s_infinite]" />
            Early Access · UAE-Focused · Now Live
          </div>

          <h1 className="font-['Cabinet_Grotesk',sans-serif] font-black text-[clamp(52px,9vw,104px)] leading-[0.95] tracking-[-4px] max-w-[960px] mx-auto">
            Your AI hiring<br />
            <span className="bg-gradient-to-br from-[#5b4fff] via-[#a78bfa] to-[#00c9a7] bg-clip-text text-transparent">partner</span>{" "}
            <span className="text-[rgba(238,238,245,0.25)]">never</span><br />
            sleeps.
          </h1>

          <p className="mt-6 max-w-[540px] mx-auto text-[clamp(16px,2vw,19px)] text-[#8080a0] leading-[1.75] font-normal">
            Rico is your AI-native UAE career companion. It learns your goals, hunts jobs in the background, explains every match, and helps you apply — so you can focus on living.
          </p>

          <div className="flex gap-3.5 items-center justify-center mt-11 flex-wrap">
            <a href="https://form.jotform.com/261278237812056" target="_blank" rel="noopener noreferrer" className="relative overflow-hidden bg-[#5b4fff] text-white px-[34px] py-[15px] rounded-xl text-[16px] font-semibold no-underline flex items-center gap-2 shadow-[0_8px_32px_rgba(91,79,255,0.3)] transition-all hover:translate-y-[-2px] hover:shadow-[0_14px_48px_rgba(91,79,255,0.3)] group">
              <span className="absolute inset-0 bg-gradient-to-br from-[rgba(255,255,255,0.12)] to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <LightningIcon />
              Start for free
            </a>
            <a href="#how" className="text-[#8080a0] px-6 py-[15px] text-[15px] font-medium no-underline transition-colors hover:text-[#eeeef5] flex items-center gap-1.5 group">
              See how it works
              <span className="transition-transform group-hover:translate-x-[3px]"><ArrowRightIcon /></span>
            </a>
          </div>

          <div className="flex items-center justify-center gap-7 mt-12 flex-wrap">
            {["UAE job boards scanned daily", "English + Arabic + mixed language", "Never applies without your approval", "Telegram alerts + full dashboard"].map((t) => (
              <div key={t} className="flex items-center gap-[7px] text-[13px] text-[#5a5a7a]">
                <span className="text-[#00c9a7]"><CheckIcon /></span>
                {t}
              </div>
            ))}
          </div>

          {/* Mockup */}
          <div className="mt-[72px] w-full max-w-[920px] mx-auto relative z-[1]">
            <div className="absolute inset-[-80px] bg-[radial-gradient(ellipse_at_50%_30%,rgba(91,79,255,0.14)_0%,transparent_65%)] pointer-events-none" />
            <div className="bg-[#0d0d1f] border border-[rgba(255,255,255,0.1)] rounded-[18px] overflow-hidden shadow-[0_48px_120px_rgba(0,0,0,0.7),inset_0_1px_0_rgba(255,255,255,0.06)] relative">
              <div className="bg-[rgba(255,255,255,0.025)] border-b border-[rgba(255,255,255,0.06)] px-[18px] py-[13px] flex items-center gap-2">
                <div className="w-[10px] h-[10px] rounded-full bg-[#ff5f57]" />
                <div className="w-[10px] h-[10px] rounded-full bg-[#febc2e]" />
                <div className="w-[10px] h-[10px] rounded-full bg-[#28c840]" />
                <div className="flex-1 text-center text-[12px] text-[#5a5a7a] font-['Instrument_Sans',sans-serif]">Rico AI — Dashboard</div>
                <div className="flex items-center gap-[5px] text-[11px] text-[#00c9a7]">
                  <span className="w-[5px] h-[5px] bg-[#00c9a7] rounded-full shadow-[0_0_6px_#00c9a7] animate-[blink_2s_infinite]" />
                  Live · UAE
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-[200px_1fr_180px]">
                {/* Sidebar */}
                <div className="hidden md:flex border-r border-[rgba(255,255,255,0.06)] p-4 flex-col gap-0.5">
                  <div className="text-[10px] uppercase tracking-wider text-[#5a5a7a] px-2 py-[10px] font-['Cabinet_Grotesk',sans-serif]">Rico</div>
                  {["Dashboard", "Job Matches", "Applications", "Chat with Rico"].map((n, i) => (
                    <div key={n} className={`px-[10px] py-2 rounded-[7px] text-[12px] flex items-center gap-2 ${i === 0 ? "bg-[rgba(91,79,255,0.12)] text-[#a78bfa] border border-[rgba(91,79,255,0.18)]" : "text-[#5a5a7a]"}`}>
                      <span className="w-[13px] h-[13px] inline-block opacity-70">{i === 0 ? "⊞" : i === 1 ? "◎" : i === 2 ? "▭" : "💬"}</span>
                      {n}
                    </div>
                  ))}
                </div>
                {/* Main */}
                <div className="p-5 flex flex-col gap-3 overflow-hidden">
                  <div className="font-['Cabinet_Grotesk',sans-serif] font-700 text-[14px] text-[#eeeef5] mb-0.5">Today&apos;s Top Matches</div>
                  <div className="text-[11px] text-[#5a5a7a]">3 new roles matched your profile · Dubai &amp; Abu Dhabi</div>
                  <MockJob ico="EM" color="bg-[rgba(0,112,243,0.15)] text-[#60a5fa]" title="Environmental Manager — HSE" company="ADNOC Group · Abu Dhabi, UAE" tags={["AED 28-35k/mo", "ISO 14001", "Senior"]} score="96%" scoreColor="text-[#00c9a7] bg-[rgba(0,201,167,0.1)]" />
                  <MockJob ico="OP" color="bg-[rgba(52,211,153,0.12)] text-[#34d399]" title="Operations Director — Facilities" company="Emaar Properties · Dubai, UAE" tags={["AED 22-28k/mo", "MBA Preferred"]} score="88%" scoreColor="text-[#00c9a7] bg-[rgba(0,201,167,0.1)]" />
                  <MockJob ico="GM" color="bg-[rgba(245,158,11,0.1)] text-[#f5a623]" title="General Manager — Waste Services" company="Averda UAE · Sharjah, UAE" tags={["AED 18-24k/mo", "Gulf Experience"]} score="74%" scoreColor="text-[#f5a623] bg-[rgba(245,166,35,0.1)]" />
                </div>
                {/* Right */}
                <div className="hidden md:flex border-l border-[rgba(255,255,255,0.06)] p-4 flex-col gap-3">
                  {[{ n: "24", l: "Jobs scanned today", c: "text-[#818cf8]" }, { n: "3", l: "Strong matches", c: "text-[#00c9a7]" }, { n: "7", l: "Apps tracked", c: "text-[#f5a623]" }].map((s) => (
                    <div key={s.l} className="bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-[9px] p-3 text-center">
                      <div className={`font-['Cabinet_Grotesk',sans-serif] font-black text-[22px] tracking-[-1px] ${s.c}`}>{s.n}</div>
                      <div className="text-[10px] text-[#5a5a7a] mt-0.5">{s.l}</div>
                    </div>
                  ))}
                  <div className="mt-auto bg-[rgba(0,136,204,0.08)] border border-[rgba(0,136,204,0.18)] rounded-[9px] p-[10px_12px]">
                    <div className="flex items-center gap-1.5 mb-1.5"><span className="text-[14px]">✈️</span><span className="text-[11px] font-semibold text-[#60b8ff]">Telegram Alert</span></div>
                    <div className="text-[10px] text-[#5a5a7a] leading-[1.5]">🎯 Rico found 3 new matches. Tap to review &amp; approve.</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Tech bar */}
      <div className="relative z-[1] py-8 px-6 md:px-12 border-y border-[rgba(255,255,255,0.06)] flex items-center justify-center gap-6 md:gap-12 flex-wrap bg-[rgba(255,255,255,0.01)]">
        <span className="text-[11px] uppercase tracking-wider text-[#5a5a7a] font-semibold">Powered by</span>
        {TECH_PILLS.map((p) => (
          <div key={p.label} className="flex items-center gap-[7px] text-[13px] text-[#8080a0] font-medium">
            <span>{p.emoji}</span>
            {p.label}
          </div>
        ))}
      </div>

      {/* How it works */}
      <section id="how" className="relative z-[1] py-28 px-6 md:px-12 max-w-[1140px] mx-auto">
        <Reveal>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-[#5b4fff] font-700 mb-3.5">
            <span className="w-5 h-px bg-[#5b4fff]" />
            How it works
          </div>
        </Reveal>
        <Reveal>
          <h2 className="font-['Cabinet_Grotesk',sans-serif] font-black text-[clamp(36px,5vw,60px)] tracking-[-2.5px] leading-[1] max-w-[660px] mb-[72px]">
            From first message to <span className="text-[#5a5a7a]">dream job.</span>
          </h2>
        </Reveal>
        <Reveal>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-8 lg:gap-0 relative">
            <div className="hidden lg:block absolute top-8 left-[10%] right-[10%] h-px bg-gradient-to-r from-transparent via-[rgba(255,255,255,0.1)] via-[#5b4fff] via-[#00c9a7] to-transparent" />
            {FLOW_STEPS.map((s) => (
              <div key={s.num} className="relative z-[1] text-center px-3 group">
                <div className="w-16 h-16 rounded-full bg-[#13132a] border border-[rgba(255,255,255,0.1)] flex items-center justify-center mx-auto mb-6 font-['Cabinet_Grotesk',sans-serif] font-black text-[20px] text-[#8080a0] transition-all group-hover:bg-[rgba(91,79,255,0.15)] group-hover:border-[#5b4fff] group-hover:text-[#eeeef5] group-hover:shadow-[0_0_28px_rgba(91,79,255,0.3)]">
                  {s.num}
                </div>
                <span className="text-[24px] block mb-5">{s.icon}</span>
                <div className="font-['Cabinet_Grotesk',sans-serif] font-700 text-[15px] mb-2 tracking-[-0.2px]">{s.title}</div>
                <div className="text-[13px] text-[#5a5a7a] leading-[1.65]">{s.desc}</div>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      {/* Features */}
      <section id="features" className="relative z-[1] py-28 px-6 md:px-12 max-w-[1140px] mx-auto">
        <Reveal>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-[#5b4fff] font-700 mb-3.5">
            <span className="w-5 h-px bg-[#5b4fff]" />
            What Rico does
          </div>
        </Reveal>
        <Reveal>
          <h2 className="font-['Cabinet_Grotesk',sans-serif] font-black text-[clamp(36px,5vw,60px)] tracking-[-2.5px] leading-[1] max-w-[660px] mb-[72px]">
            Every tool your <span className="text-[#5a5a7a]">career needs,</span><br />working for you.
          </h2>
        </Reveal>
        <Reveal>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-[rgba(255,255,255,0.06)] border border-[rgba(255,255,255,0.06)] rounded-[20px] overflow-hidden">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-[#06060f] p-10 md:p-8 relative overflow-hidden transition-colors hover:bg-[rgba(91,79,255,0.03)] group">
                <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-[#5b4fff] to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="w-[46px] h-[46px] rounded-[11px] mb-[22px] bg-[rgba(91,79,255,0.09)] border border-[rgba(91,79,255,0.18)] flex items-center justify-center text-[21px]">{f.icon}</div>
                <div className="font-['Cabinet_Grotesk',sans-serif] font-700 text-[17px] mb-2.5 tracking-[-0.3px]">{f.title}</div>
                <div className="text-[14px] text-[#5a5a7a] leading-[1.7]">{f.desc}</div>
                <div className="inline-flex items-center gap-[5px] mt-3.5 font-mono text-[11px] text-[#00c9a7] bg-[rgba(0,201,167,0.07)] border border-[rgba(0,201,167,0.15)] rounded-[5px] px-2 py-[3px]">
                  {f.endpoint}
                  {f.note && <span className="text-[#5a5a7a] ml-1">· {f.note}</span>}
                </div>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      {/* Free mode notice */}
      <section className="relative z-[1] py-10 px-6 md:px-12 max-w-[1140px] mx-auto">
        <Reveal>
          <div className="bg-[rgba(245,166,35,0.04)] border border-[rgba(245,166,35,0.15)] rounded-xl p-5 flex items-start gap-3">
            <span className="text-[20px]">⚡</span>
            <div>
              <div className="text-[14px] font-semibold text-[#f5a623]">Running in free mode</div>
              <div className="text-[13px] text-[#5a5a7a] mt-1 leading-relaxed">
                OpenAI credits are temporarily unavailable, so Rico is running on a fallback mode. All core features work — job matching, chat, and tracking — but responses may be simpler. Full AI power returns once credits are restored.
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      {/* API */}
      <section id="api" className="relative z-[1] py-28 px-6 md:px-12 bg-[#0d0d1f] border-y border-[rgba(255,255,255,0.06)]">
        <div className="max-w-[1140px] mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-start">
          <div>
            <Reveal>
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-[#5b4fff] font-700 mb-3.5">
                <span className="w-5 h-px bg-[#5b4fff]" />
                Developer API
              </div>
            </Reveal>
            <Reveal>
              <h2 className="font-['Cabinet_Grotesk',sans-serif] font-black text-[clamp(36px,5vw,60px)] tracking-[-2.5px] leading-[1] mb-8">
                Real endpoints.<br /><span className="text-[#5a5a7a]">Real system.</span>
              </h2>
            </Reveal>
            <Reveal>
              <p className="text-[15px] text-[#8080a0] leading-[1.75] mb-10">
                Rico runs on a production FastAPI server with Jotform onboarding webhooks, Telegram bot integration, and the full job automation pipeline. Built on Python 3.11+, Neon PostgreSQL, OpenAI tool-calling, and Redis workers.
              </p>
            </Reveal>
            <Reveal>
              <div className="flex flex-col gap-3">
                {ENDPOINTS.map((ep) => (
                  <div key={ep.path} className="bg-[#13132a] border border-[rgba(255,255,255,0.06)] rounded-[10px] p-[14px_18px] flex items-start gap-3.5 transition-colors hover:border-[rgba(91,79,255,0.3)]">
                    <span className={`font-mono text-[10px] font-700 px-2 py-[3px] rounded mt-0.5 tracking-wider shrink-0 ${ep.method === "GET" ? "text-[#34d399] bg-[rgba(52,211,153,0.1)] border border-[rgba(52,211,153,0.2)]" : "text-[#818cf8] bg-[rgba(129,140,248,0.1)] border border-[rgba(129,140,248,0.2)]"}`}>{ep.method}</span>
                    <div>
                      <div className="font-mono text-[13px] text-[#eeeef5] mb-[3px]">{ep.path}</div>
                      <div className="text-[12px] text-[#5a5a7a]">{ep.desc}</div>
                      <span className="inline-flex text-[10px] px-[7px] py-[2px] rounded text-[#8080a0] bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.06)] mt-1">{ep.tag}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
          <Reveal>
            <div className="bg-[#06060f] border border-[rgba(255,255,255,0.06)] rounded-[14px] overflow-hidden shadow-[0_24px_64px_rgba(0,0,0,0.4)]">
              <div className="bg-[rgba(255,255,255,0.025)] border-b border-[rgba(255,255,255,0.06)] px-4 py-3 flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
                  <div className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
                  <div className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
                </div>
                <div className="flex-1 text-center text-[11px] text-[#5a5a7a] font-mono">chat_request.sh</div>
              </div>
              <pre className="p-6 font-mono text-[12px] leading-[1.75] overflow-x-auto text-[#c9d1d9]">
                <span className="text-[#6272a4]"># Health check</span>{"\n"}
                <span className="text-[#50fa7b]">curl</span> http://localhost:8000<span className="text-[#f1fa8c]">/health</span>{"\n"}{"\n"}
                <span className="text-[#6272a4]"># Ask Rico to find jobs</span>{"\n"}
                <span className="text-[#50fa7b]">curl</span> -X POST http://localhost:8000<span className="text-[#f1fa8c]">/api/v1/rico/chat</span> \{"\n"}
                -H <span className="text-[#f1fa8c]">&quot;Content-Type: application/json&quot;</span> \{"\n"}
                -d <span className="text-[#f1fa8c]">&apos;{"{"}"{"\n"}
                  &quot;user_id&quot;: &quot;your_id&quot;,{"\n"}
                  &quot;message&quot;: &quot;Find HSE Manager jobs in Dubai"{"\n"}
                  {"}"}&apos;</span>{"\n"}{"\n"}
                <span className="text-[#6272a4]"># Response</span>{"\n"}
                {"{"}{"\n"}
                <span className="text-[#ff79c6]">&quot;reply&quot;</span>: <span className="text-[#f1fa8c]">&quot;Found 4 strong matches...&quot;</span>,{"\n"}
                <span className="text-[#ff79c6]">&quot;jobs&quot;</span>: [{"\n"}
                {"{"}{"\n"}
                <span className="text-[#ff79c6]">&quot;title&quot;</span>: <span className="text-[#f1fa8c]">&quot;HSE Manager&quot;</span>,{"\n"}
                <span className="text-[#ff79c6]">&quot;company&quot;</span>: <span className="text-[#f1fa8c]">&quot;ADNOC&quot;</span>,{"\n"}
                <span className="text-[#ff79c6]">&quot;score&quot;</span>: <span className="text-[#ffb86c]">94</span>,{"\n"}
                <span className="text-[#ff79c6]">&quot;reason&quot;</span>: <span className="text-[#f1fa8c]">&quot;Title + ISO 14001 match&quot;</span>{"\n"}
                {"}"}{"\n"}
                ]{"\n"}
                {"}"}
              </pre>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Integrations */}
      <section className="relative z-[1] py-28 px-6 md:px-12 max-w-[1140px] mx-auto">
        <Reveal>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-[#5b4fff] font-700 mb-3.5">
            <span className="w-5 h-px bg-[#5b4fff]" />
            Integrations
          </div>
        </Reveal>
        <Reveal>
          <h2 className="font-['Cabinet_Grotesk',sans-serif] font-black text-[clamp(36px,5vw,60px)] tracking-[-2.5px] leading-[1] mb-[72px]">
            Every tool <span className="text-[#5a5a7a]">connected.</span>
          </h2>
        </Reveal>
        <Reveal>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {INTEGRATIONS.map((i) => (
              <div key={i.name} className="bg-[#0d0d1f] border border-[rgba(255,255,255,0.06)] rounded-[14px] p-6 text-center transition-all hover:border-[rgba(91,79,255,0.3)] hover:-translate-y-[3px] hover:shadow-[0_12px_36px_rgba(0,0,0,0.3)]">
                <span className="text-[32px] block mb-3">{i.icon}</span>
                <div className="font-['Cabinet_Grotesk',sans-serif] font-700 text-[15px] mb-1">{i.name}</div>
                <div className="text-[12px] text-[#5a5a7a]">{i.role}</div>
                {i.status === "planned" && <div className="text-[10px] text-[#f5a623] mt-2">Planned</div>}
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      {/* Safety */}
      <section className="relative z-[1] py-28 px-6 md:px-12 max-w-[1140px] mx-auto">
        <Reveal>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-[#5b4fff] font-700 mb-3.5">
            <span className="w-5 h-px bg-[#5b4fff]" />
            Built with trust
          </div>
        </Reveal>
        <Reveal>
          <h2 className="font-['Cabinet_Grotesk',sans-serif] font-black text-[clamp(36px,5vw,60px)] tracking-[-2.5px] leading-[1] mb-[72px]">
            Rico&apos;s rules.<br /><span className="text-[#5a5a7a]">No exceptions.</span>
          </h2>
        </Reveal>
        <Reveal>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-[#0d0d1f] border border-[rgba(255,255,255,0.06)] rounded-[14px] p-7 border-t-2 border-t-[#00c9a7]">
              <div className="flex items-center gap-2.5 mb-4 font-['Cabinet_Grotesk',sans-serif] font-700 text-[15px]"><span>✅</span> Rico always</div>
              <ul className="flex flex-col gap-2">
                {SAFETY_ALWAYS.map((item) => (
                  <li key={item} className="flex items-start gap-2 text-[13px] text-[#5a5a7a]"><span className="text-[#00c9a7] shrink-0 mt-0.5">✓</span>{item}</li>
                ))}
              </ul>
            </div>
            <div className="bg-[#0d0d1f] border border-[rgba(255,255,255,0.06)] rounded-[14px] p-7 border-t-2 border-t-[rgba(255,94,91,0.4)]">
              <div className="flex items-center gap-2.5 mb-4 font-['Cabinet_Grotesk',sans-serif] font-700 text-[15px]"><span>🚫</span> Rico never</div>
              <ul className="flex flex-col gap-2">
                {SAFETY_NEVER.map((item) => (
                  <li key={item} className="flex items-start gap-2 text-[13px] text-[#5a5a7a]"><span className="text-[#ff5e5b] shrink-0 mt-0.5">✗</span>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </Reveal>
      </section>

      {/* CTA */}
      <div className="relative z-[1] py-20 px-6 md:px-12 pb-[120px] text-center">
        <Reveal>
          <div className="max-w-[780px] mx-auto bg-[#0d0d1f] border border-[rgba(255,255,255,0.1)] rounded-[28px] p-12 md:p-20 relative overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,rgba(91,79,255,0.15)_0%,transparent_65%)] pointer-events-none" />
            <div className="relative z-[1]">
              <div className="font-['Cabinet_Grotesk',sans-serif] font-black text-[clamp(36px,5vw,60px)] tracking-[-2.5px] leading-[1] mb-5">
                Stop hunting.<br />
                <span className="bg-gradient-to-br from-[#5b4fff] to-[#00c9a7] bg-clip-text text-transparent">Let Rico hunt.</span>
              </div>
              <p className="text-[18px] text-[#8080a0] max-w-[480px] mx-auto mb-11 leading-[1.7]">
                Set up your profile in 60 seconds. Rico handles the rest — every single day.
              </p>
              <div className="flex gap-3.5 justify-center flex-wrap">
                <a href="https://form.jotform.com/261278237812056" target="_blank" rel="noopener noreferrer" className="relative overflow-hidden bg-[#5b4fff] text-white px-10 py-[17px] rounded-xl text-[17px] font-semibold no-underline flex items-center gap-2 shadow-[0_8px_32px_rgba(91,79,255,0.3)] transition-all hover:translate-y-[-2px] hover:shadow-[0_14px_48px_rgba(91,79,255,0.3)] group">
                  <span className="absolute inset-0 bg-gradient-to-br from-[rgba(255,255,255,0.12)] to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                  <LightningIcon />
                  Start your job search
                </a>
                <Link href="/dashboard" className="bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-[#8080a0] px-8 py-[17px] rounded-xl text-[16px] font-semibold no-underline transition-all hover:text-[#eeeef5] hover:border-[rgba(255,255,255,0.15)] flex items-center gap-2">
                  View dashboard →
                </Link>
              </div>
              <p className="mt-6 text-[13px] text-[#5a5a7a]">Free early access · UAE job seekers · No spam, ever</p>
            </div>
          </div>
        </Reveal>
      </div>

      {/* Footer */}
      <footer className="relative z-[1] border-t border-[rgba(255,255,255,0.06)] px-6 md:px-12 py-12 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <Link href="/" className="flex items-center gap-2 font-['Cabinet_Grotesk',sans-serif] font-black text-[16px] text-[#eeeef5] no-underline">
          <div className="w-7 h-7 rounded-[9px] bg-gradient-to-br from-[#5b4fff] to-[#8b5cf6] flex items-center justify-center text-[13px] font-black text-white">R</div>
          Rico AI
        </Link>
        <div className="flex gap-6">
          <a href="https://form.jotform.com/261278237812056" target="_blank" rel="noopener noreferrer" className="text-[13px] text-[#5a5a7a] no-underline hover:text-[#eeeef5] transition-colors">Get Started</a>
          <a href="https://github.com/Binz2008-star/job-automation-system-1" target="_blank" rel="noopener noreferrer" className="text-[13px] text-[#5a5a7a] no-underline hover:text-[#eeeef5] transition-colors">GitHub</a>
          <a href="#api" className="text-[13px] text-[#5a5a7a] no-underline hover:text-[#eeeef5] transition-colors">API Docs</a>
          <Link href="/login" className="text-[13px] text-[#5a5a7a] no-underline hover:text-[#eeeef5] transition-colors">Log in</Link>
        </div>
        <div className="text-[12px] text-[#5a5a7a]">© 2026 Rico AI · Built for UAE job seekers</div>
      </footer>
    </div>
  );
}
