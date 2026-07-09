"use client";

/**
 * Atelier Console — /design-gallery reference entry.
 *
 * Ported from the Lovable "Atelier" prototype (`src/routes/rico.tsx`). The
 * TanStack route wrapper and the server-fn chat have been stripped; the scripted
 * walkthrough (SCRIPT) auto-plays as the demo, and the composer's live-send is
 * reference-only (no real chat/job/apply/save/CV action). All data is sample/
 * demo. Theme/lang are scoped to this component's wrapper (see ./i18n, ./index),
 * never to <html>.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { type LiveEntry } from "./rico-schemas";
import {
  useRicoDict,
  type RicoDict,
  type RicoUI,
  type Step,
} from "./rico-content";
import { useLang, LangToggle, ThemeToggle } from "./i18n";
import {
  ArrowUp,
  Command,
  Paperclip,
  Sparkle,
  Square,
  PanelLeft,
  PanelRight,
  FileText,
  FilePlus2,
  Search as SearchIcon,
  AlertTriangle,
  RotateCcw,
  MapPin,
  Building2,
  Wallet,
  CalendarClock,
  Bell,
  Send,
  Check,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import { PrototypeNoticeToast, showPrototypeNotice } from "./prototype-notice";

/* ------------------------------------------------------------------ */
/*  Runner                                                             */
/* ------------------------------------------------------------------ */

type Rendered = { id: number; step: Step; state: "streaming" | "done" };

function loadLive(): LiveEntry[] {
  // Gallery reference: no persistence — always replay the scripted walkthrough.
  return [];
}

function saveLive(_entries: LiveEntry[]) {
  /* Gallery reference: no persistence. */
}

function liveToRendered(entries: LiveEntry[], ui: RicoUI): Rendered[] {
  const out: Rendered[] = [];
  let id = 100000;
  for (const e of entries) {
    if (e.role === "user") {
      out.push({
        id: id++,
        step: { kind: "user", text: e.text },
        state: "done",
      });
      continue;
    }
    if (e.kind === "text" || e.kind === "no_match") {
      out.push({
        id: id++,
        step: { kind: "say", text: e.text, ms: 0 },
        state: "done",
      });
    } else if (e.kind === "jobs") {
      out.push({
        id: id++,
        step: { kind: "say", text: e.text, ms: 0 },
        state: "done",
      });
      for (const j of e.jobs) {
        out.push({
          id: id++,
          step: {
            kind: "jobmatch",
            role: j.role,
            company: j.company,
            city: j.city,
            salary: j.salary,
            posted: j.posted,
            score: j.score,
            why: j.why,
            gaps: j.gaps,
            recommended: false,
          },
          state: "done",
        });
      }
    } else if (e.kind === "error") {
      out.push({
        id: id++,
        step: {
          kind: "error",
          name: "rico.reply",
          arg: "",
          message: e.text,
          retryNote: ui.live.retryFromComposer,
        },
        state: "done",
      });
    } else if (e.kind === "stopped") {
      out.push({
        id: id++,
        step: { kind: "say", text: `— ${e.text}`, ms: 0 },
        state: "done",
      });
    }
  }
  return out;
}

export function RicoChat() {
  const dict = useRicoDict();
  const { lang } = useLang();
  const isAr = lang === "ar";
  const SCRIPT = dict.script;
  const ui = dict.ui;

  // Reference-only: no live chat server-fn. `live`/`handedOver` stay inert
  // (the composer never sends), so the right rail derives entirely from the
  // scripted walkthrough.
  const [live] = useState<LiveEntry[]>([]);
  const [handedOver] = useState<boolean>(false);
  const [pending] = useState(false);
  const [hydratedFromStorage, setHydratedFromStorage] = useState(false);

  const [items, setItems] = useState<Rendered[]>([]);
  const [running, setRunning] = useState<boolean>(false);
  const [cursor, setCursor] = useState<number>(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // Reference-only: always start the scripted walkthrough fresh on mount.
    loadLive();
    setRunning(true);
    setHydratedFromStorage(true);
    // Run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!running) return;
    if (cursor >= SCRIPT.length) {
      setRunning(false);
      return;
    }
    const step = SCRIPT[cursor];
    const id = cursor;
    setItems((prev) => [...prev, { id, step, state: "streaming" }]);

    const dwell =
      step.kind === "user"
        ? 250
        : step.kind === "think"
          ? 900
          : step.kind === "plan"
            ? 1200
            : step.kind === "check"
              ? 500
              : step.kind === "error"
                ? 1400
                : step.kind === "ask"
                  ? 2200
                  : step.kind === "form"
                    ? Math.max(2600, step.fields.length * 700 + 900)
                    : step.kind === "jobmatch"
                      ? 1600
                      : step.kind === "cvdiff"
                        ? Math.max(3200, step.bullets.length * 900 + 1400)
                        : step.kind === "tracker"
                          ? Math.max(2200, step.stages.length * 260 + 1400)
                          : step.kind === "reminder"
                            ? 2600
                            : step.kind === "analytics"
                              ? Math.max(
                                  3400,
                                  step.funnel.length * 300 +
                                    step.insights.length * 400 +
                                    1400,
                                )
                              : step.kind === "say"
                                ? Math.max(
                                    1200,
                                    step.text.length * (step.ms ?? 18),
                                  )
                                : step.kind === "tool"
                                  ? (step.ms ?? 1000)
                                  : step.kind === "decision"
                                    ? 1400
                                    : step.kind === "diff"
                                      ? 1600
                                      : 900;

    const t = window.setTimeout(() => {
      setItems((prev) =>
        prev.map((r) => (r.id === id ? { ...r, state: "done" } : r)),
      );
      setCursor((c) => c + 1);
    }, dwell);
    return () => window.clearTimeout(t);
  }, [cursor, running, SCRIPT]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [items, live, pending]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!hydratedFromStorage) return;
    saveLive(live);
  }, [live, hydratedFromStorage]);

  const busy = running || pending;
  const status = pending
    ? ui.status.replying
    : running
      ? ui.status.working
      : handedOver
        ? ui.status.live
        : ui.status.ready;

  const checkedSet = useMemo(() => {
    const s = new Set<string>();
    for (const r of items) {
      if (r.step.kind === "check" && r.state === "done") s.add(r.step.item);
    }
    return s;
  }, [items]);

  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);

  const liveRendered = useMemo(() => liveToRendered(live, ui), [live, ui]);
  const allItems = useMemo(
    () => (handedOver ? [...items, ...liveRendered] : items),
    [items, liveRendered, handedOver],
  );

  const shortlist = useMemo(() => {
    return allItems
      .filter(
        (r): r is Rendered & { step: Extract<Step, { kind: "jobmatch" }> } =>
          r.step.kind === "jobmatch",
      )
      .map((r) => r.step);
  }, [allItems]);

  const pipeline = useMemo(() => {
    const byJob = new Map<string, Extract<Step, { kind: "tracker" }>>();
    for (const r of allItems) {
      if (r.step.kind !== "tracker") continue;
      byJob.set(r.step.jobRef, r.step);
    }
    return Array.from(byJob.values());
  }, [allItems]);

  const touchedFiles = useMemo(() => {
    const seen = new Map<
      string,
      { path: string; op: "read" | "write" | "grep"; latestId: number }
    >();
    for (const r of allItems) {
      if (r.step.kind !== "tool") continue;
      const t = r.step;
      let op: "read" | "write" | "grep" | null = null;
      if (t.name.startsWith("read")) op = "read";
      else if (t.name.startsWith("write") || t.name.startsWith("edit"))
        op = "write";
      else if (
        t.name.startsWith("grep") ||
        t.name.startsWith("search") ||
        t.name.startsWith("score") ||
        t.name.startsWith("enrich")
      )
        op = "grep";
      if (!op) continue;
      seen.set(t.arg, { path: t.arg, op, latestId: r.id });
    }
    return Array.from(seen.values()).sort((a, b) => b.latestId - a.latestId);
  }, [allItems]);

  function handleSend(_text: string) {
    // Reference-only: live chat is disabled in the gallery. The scripted
    // walkthrough is the demo; the composer does not send real messages.
    showPrototypeNotice("forbidden");
  }

  function handleStop() {
    // Stops the scripted walkthrough playback (reference-only control).
    if (running) setRunning(false);
  }

  function handleRestart() {
    // Replays the scripted walkthrough from the top (reference-only control).
    setItems([]);
    setCursor(0);
    setRunning(true);
  }


  return (
    <div
      dir={isAr ? "rtl" : "ltr"}
      lang={lang}
      className="min-h-screen bg-[var(--paper)] text-[var(--ink)] flex flex-col"
    >
      <PrototypeNoticeToast />
      <TopBar
        status={status}
        running={busy}
        leftOpen={leftOpen}
        rightOpen={rightOpen}
        onToggleLeft={() => setLeftOpen((v) => !v)}
        onToggleRight={() => setRightOpen((v) => !v)}
        ui={ui}
      />

      <div className="flex-1 min-h-0 flex">
        <SessionsRail
          open={leftOpen}
          onClose={() => setLeftOpen(false)}
          dict={dict}
        />

        <div className="flex-1 min-w-0 flex flex-col">
          <div ref={scrollRef} className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[720px] px-6 md:px-8 py-10 md:py-14">
              {/* opening slug */}
              <div className="mb-10 flex flex-wrap items-baseline gap-x-3 gap-y-1.5 border-b border-[var(--rule)]/70 pb-4">
                <span
                  dir="ltr"
                  className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]"
                >
                  {ui.slug.sessionPrefix}
                </span>
                <span
                  title={ui.slug.sampleTooltip}
                  className="inline-flex items-center rounded-[3px] border border-[var(--sun)]/70 bg-[var(--sun)]/5 px-1.5 py-[1px] font-mono text-[9px] uppercase tracking-[0.22em] text-[var(--sun)]"
                >
                  {ui.slug.sampleDemo}
                </span>
                <span className="ms-auto font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
                  {handedOver ? ui.slug.liveUAE : ui.slug.jobHuntUAE}
                </span>
              </div>

              <div className="flex flex-col gap-6">
                {allItems.map((r) => (
                  <StepView key={r.id} r={r} checked={checkedSet} ui={ui} />
                ))}
                {busy && <Cursor ui={ui} />}
              </div>
            </div>
          </div>

          <Composer
            inputRef={inputRef}
            running={running}
            pending={pending}
            onStop={handleStop}
            onRestart={handleRestart}
            onSend={handleSend}
            ui={ui}
          />
        </div>

        <ShortlistRail
          open={rightOpen}
          shortlist={shortlist}
          files={touchedFiles}
          pipeline={pipeline}
          ui={ui}
        />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Top bar                                                            */
/* ------------------------------------------------------------------ */

function TopBar({
  status,
  running,
  leftOpen,
  rightOpen,
  onToggleLeft,
  onToggleRight,
  ui,
}: {
  status: string;
  running: boolean;
  leftOpen: boolean;
  rightOpen: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  ui: RicoUI;
}) {
  return (
    <header className="sticky top-0 z-30 bg-[var(--paper)]/85 backdrop-blur border-b border-[var(--rule)]/70">
      <div className="px-4 md:px-6 h-12 flex items-center gap-3">
        <button
          onClick={onToggleLeft}
          aria-label={ui.top.toggleSessions}
          className={`p-1.5 rounded-md transition-colors ${
            leftOpen ? "text-[var(--ink)]" : "text-[var(--ink-mute)]"
          } hover:bg-[var(--paper-2)]`}
        >
          <PanelLeft className="w-4 h-4 rtl:-scale-x-100" />
        </button>
        <span className="font-display text-[15px] leading-none tracking-tight select-none">
          Rico
        </span>
        <span className="hidden sm:inline font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
          {ui.top.workspaceTag}
        </span>
        <span className="ms-auto flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              running
                ? "bg-[var(--sun)] animate-pulse"
                : "bg-[var(--ink-mute)]/40"
            }`}
          />
          {status}
        </span>
        <LangToggle className="ms-2" />
        <ThemeToggle />
        <button
          onClick={onToggleRight}
          aria-label={ui.top.toggleShortlist}
          className={`ms-2 p-1.5 rounded-md transition-colors ${
            rightOpen ? "text-[var(--ink)]" : "text-[var(--ink-mute)]"
          } hover:bg-[var(--paper-2)]`}
        >
          <PanelRight className="w-4 h-4 rtl:-scale-x-100" />
        </button>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/*  Sessions rail (left)                                               */
/* ------------------------------------------------------------------ */

function SessionsRail({
  open,
  dict,
}: {
  open: boolean;
  onClose: () => void;
  dict: RicoDict;
}) {
  const { sessions } = dict;
  const ui = dict.ui;
  return (
    <aside
      className={`hidden md:flex flex-col border-e border-[var(--rule)]/70 bg-[var(--paper)]/60 transition-[width] duration-300 overflow-hidden ${
        open ? "w-[260px]" : "w-0"
      }`}
    >
      <div className="w-[260px] flex-1 min-h-0 flex flex-col p-4">
        <div className="flex items-center justify-between mb-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            {ui.sessions.title}
          </span>
          <button className="font-mono text-[11px] text-[var(--ink)] hover:text-[var(--sun)] transition-colors">
            {ui.sessions.newBtn}
          </button>
        </div>
        <ul className="flex-1 overflow-y-auto -mx-1 space-y-0.5">
          {sessions.map((s) => (
            <li key={s.id}>
              <button
                className={`group w-full text-start px-2 py-1.5 rounded-md flex items-baseline gap-2 transition-colors ${
                  s.active
                    ? "bg-[var(--card)] text-[var(--ink)]"
                    : "text-[var(--ink-soft)] hover:bg-[var(--paper-2)]"
                }`}
              >
                {s.active && (
                  <span className="h-1 w-1 rounded-full bg-[var(--sun)] shrink-0 translate-y-[-2px]" />
                )}
                <span className="flex-1 min-w-0 truncate text-[13px] leading-snug">
                  {s.title}
                </span>
                <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--ink-mute)]/80 shrink-0">
                  {s.when}
                </span>
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-4 pt-3 border-t border-[var(--rule)]/70 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
          {sessions.length} {ui.sessions.threadsSuffix}
        </div>
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/*  Shortlist rail (right)                                             */
/* ------------------------------------------------------------------ */

function ShortlistRail({
  open,
  shortlist,
  files,
  pipeline,
  ui,
}: {
  open: boolean;
  shortlist: Extract<Step, { kind: "jobmatch" }>[];
  files: { path: string; op: "read" | "write" | "grep"; latestId: number }[];
  pipeline: Extract<Step, { kind: "tracker" }>[];
  ui: RicoUI;
}) {
  return (
    <aside
      className={`hidden lg:flex flex-col border-s border-[var(--rule)]/70 bg-[var(--paper)]/60 transition-[width] duration-300 overflow-hidden ${
        open ? "w-[300px]" : "w-0"
      }`}
    >
      <div className="w-[300px] flex-1 min-h-0 flex flex-col p-4">
        <div className="flex items-center justify-between mb-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            {ui.shortlistRail.shortlist}
          </span>
          <span
            dir="ltr"
            className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink)]"
          >
            {shortlist.length}
          </span>
        </div>

        {shortlist.length === 0 ? (
          <p className="text-[13px] italic text-[var(--ink-mute)] leading-relaxed">
            {ui.shortlistRail.empty}
          </p>
        ) : (
          <ul className="space-y-2">
            {shortlist.map((j) => (
              <li
                key={j.role + j.company}
                className="group p-2.5 rounded-md border border-[var(--rule)]/70 bg-[var(--card)] hover:border-[var(--ink)]/50 transition-colors"
              >
                <div className="flex items-baseline justify-between gap-2 mb-1">
                  <span className="font-display text-[13px] leading-tight text-[var(--ink)] truncate">
                    {j.company}
                  </span>
                  <ScorePip score={j.score} small ui={ui} />
                </div>
                <div className="font-mono text-[10.5px] text-[var(--ink-soft)] truncate">
                  {j.role}
                </div>
                <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--ink-mute)] truncate">
                  {j.city}
                </div>
                {j.recommended && (
                  <div className="mt-1.5 inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.22em] text-[var(--sun)]">
                    <Sparkle className="w-2.5 h-2.5" />{" "}
                    {ui.shortlistRail.ricoPicks}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}

        {pipeline.length > 0 && (
          <>
            <div className="mt-5 mb-2 flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
                {ui.shortlistRail.pipeline}
              </span>
              <span
                dir="ltr"
                className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink)]"
              >
                {pipeline.length}
              </span>
            </div>
            <ul className="space-y-1.5">
              {pipeline.map((p) => {
                const rawStage = p.stages[p.current] ?? "applied";
                const stage =
                  ui.tracker.stageNames[rawStage] ?? rawStage;
                return (
                  <li
                    key={p.jobRef}
                    className="p-2 rounded-md border border-[var(--rule)]/70 bg-[var(--card)]"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-display text-[12.5px] leading-tight text-[var(--ink)] truncate">
                        {p.company}
                      </span>
                      <span className="shrink-0 font-mono text-[9px] uppercase tracking-[0.22em] text-[var(--sun)]">
                        {stage}
                      </span>
                    </div>
                    <div className="mt-1.5 flex items-center gap-[3px]">
                      {p.stages.map((_, i) => (
                        <span
                          key={i}
                          className={`h-[3px] flex-1 rounded-full ${
                            i < p.current
                              ? "bg-[var(--ink)]/60"
                              : i === p.current
                                ? "bg-[var(--sun)]"
                                : "bg-[var(--rule)]"
                          }`}
                        />
                      ))}
                    </div>
                    <div className="mt-1 font-mono text-[9.5px] uppercase tracking-[0.2em] text-[var(--ink-mute)] truncate">
                      {ui.shortlistRail.nextPrefix} {p.nextCheck}
                    </div>
                  </li>
                );
              })}
            </ul>
          </>
        )}

        {files.length > 0 && (
          <>
            <div className="mt-5 mb-2 flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
                {ui.shortlistRail.signal}
              </span>
              <span
                dir="ltr"
                className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink)]"
              >
                {files.length}
              </span>
            </div>
            <ul className="space-y-0.5">
              {files.slice(0, 6).map((f) => {
                const Icon =
                  f.op === "write"
                    ? FilePlus2
                    : f.op === "grep"
                      ? SearchIcon
                      : FileText;
                const tone =
                  f.op === "write"
                    ? "text-[var(--sun)]"
                    : "text-[var(--ink-mute)]";
                return (
                  <li
                    key={f.path}
                    className="flex items-baseline gap-2 py-0.5 px-1"
                  >
                    <Icon
                      className={`w-3 h-3 shrink-0 ${tone} translate-y-[2px]`}
                    />
                    <span
                      dir="ltr"
                      className="flex-1 min-w-0 font-mono text-[11px] text-[var(--ink-soft)] truncate"
                    >
                      {f.path}
                    </span>
                    <span
                      className={`font-mono text-[9px] uppercase tracking-[0.2em] shrink-0 ${
                        f.op === "write"
                          ? "text-[var(--sun)]"
                          : "text-[var(--ink-mute)]"
                      }`}
                    >
                      {f.op}
                    </span>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/*  Step renderers                                                     */
/* ------------------------------------------------------------------ */

function StepView({
  r,
  checked,
  ui,
}: {
  r: Rendered;
  checked: Set<string>;
  ui: RicoUI;
}) {
  const { step } = r;
  switch (step.kind) {
    case "user":
      return <UserLine text={step.text} ui={ui} />;
    case "think":
      return <ThinkLine text={step.text} ui={ui} />;
    case "say":
      return (
        <SayLine
          text={step.text}
          typing={r.state === "streaming"}
          ms={step.ms ?? 18}
          ui={ui}
        />
      );
    case "tool":
      return <ToolLine step={step} running={r.state === "streaming"} ui={ui} />;
    case "decision":
      return <DecisionLine step={step} ui={ui} />;
    case "diff":
      return <DiffLine step={step} ui={ui} />;
    case "plan":
      return <PlanLine items={step.items} checked={checked} ui={ui} />;
    case "check":
      return <CheckLine item={step.item} ui={ui} />;
    case "error":
      return <ErrorLine step={step} ui={ui} />;
    case "ask":
      return <AskLine step={step} answered={r.state === "done"} ui={ui} />;
    case "form":
      return <FormLine step={step} committed={r.state === "done"} ui={ui} />;
    case "jobmatch":
      return (
        <JobMatchLine step={step} arriving={r.state === "streaming"} ui={ui} />
      );
    case "cvdiff":
      return (
        <CvDiffLine step={step} arriving={r.state === "streaming"} ui={ui} />
      );
    case "tracker":
      return (
        <TrackerLine step={step} arriving={r.state === "streaming"} ui={ui} />
      );
    case "reminder":
      return (
        <ReminderLine step={step} arriving={r.state === "streaming"} ui={ui} />
      );
    case "analytics":
      return (
        <AnalyticsLine step={step} arriving={r.state === "streaming"} ui={ui} />
      );
    case "done":
      return <DoneLine text={step.text} suggestions={step.suggestions} />;
  }
}

function Gutter({
  label,
  tone = "mute",
}: {
  label: string;
  tone?: "mute" | "hot" | "ink";
}) {
  const color =
    tone === "hot"
      ? "text-[var(--sun)]"
      : tone === "ink"
        ? "text-[var(--ink)]"
        : "text-[var(--ink-mute)]";
  return (
    <span
      className={`font-mono text-[10px] uppercase tracking-[0.22em] ${color} select-none min-w-[64px]`}
    >
      {label}
    </span>
  );
}

function UserLine({ text, ui }: { text: string; ui: RicoUI }) {
  return (
    <div className="flex gap-4 items-start">
      <Gutter label={ui.gutter.you} tone="ink" />
      <p className="font-display text-[22px] md:text-[26px] leading-[1.25] tracking-tight -mt-1">
        {text}
      </p>
    </div>
  );
}

function ThinkLine({ text, ui }: { text: string; ui: RicoUI }) {
  return (
    <div className="flex gap-4 items-start">
      <Gutter label={ui.gutter.think} />
      <p className="italic text-[15px] leading-relaxed text-[var(--ink-mute)]">
        {text}
      </p>
    </div>
  );
}

function SayLine({
  text,
  typing,
  ms,
  ui,
}: {
  text: string;
  typing: boolean;
  ms: number;
  ui: RicoUI;
}) {
  const shown = useTyping(text, typing, ms);
  return (
    <div className="flex gap-4 items-start">
      <Gutter label={ui.gutter.rico} tone="hot" />
      <p className="text-[16px] leading-relaxed text-[var(--ink)]">
        {shown}
        {typing && shown.length < text.length && (
          <span className="inline-block w-[7px] h-[1.05em] translate-y-[3px] bg-[var(--ink)] ms-0.5 animate-pulse" />
        )}
      </p>
    </div>
  );
}

function ToolLine({
  step,
  running,
  ui,
}: {
  step: Extract<Step, { kind: "tool" }>;
  running: boolean;
  ui: RicoUI;
}) {
  const [open, setOpen] = useState(true);
  const lines = step.lines ?? [];
  const shownCount = useLineReveal(
    lines.length,
    running,
    (step.ms ?? 1000) / Math.max(1, lines.length),
  );

  return (
    <div className="flex gap-4 items-start">
      <Gutter
        label={running ? ui.gutter.run : ui.gutter.done}
        tone={running ? "hot" : "mute"}
      />
      <div className="flex-1 min-w-0">
        <button
          onClick={() => setOpen((o) => !o)}
          className="group flex items-baseline gap-2 text-start"
        >
          <span
            dir="ltr"
            className="font-mono text-[13px] text-[var(--ink)]"
          >
            {step.name}
          </span>
          <span
            dir="ltr"
            className="font-mono text-[13px] text-[var(--ink-mute)] truncate"
          >
            ({step.arg})
          </span>
          {running ? (
            <span className="ms-1 inline-flex gap-1">
              <Dot delay={0} />
              <Dot delay={120} />
              <Dot delay={240} />
            </span>
          ) : (
            <span className="ms-1 font-mono text-[11px] text-[var(--sun)]">
              ✓ {step.note}
            </span>
          )}
        </button>
        {open && lines.length > 0 && (
          <pre
            dir="ltr"
            className="mt-1.5 font-mono text-[12.5px] leading-[1.65] text-[var(--ink-soft)] whitespace-pre-wrap border-s border-[var(--rule)] ps-3 text-start"
          >
            {lines.slice(0, shownCount).join("\n")}
            {running && shownCount < lines.length && (
              <span className="inline-block w-[6px] h-[1em] translate-y-[2px] bg-[var(--ink-soft)] ms-0.5 animate-pulse" />
            )}
          </pre>
        )}
      </div>
    </div>
  );
}

function DecisionLine({
  step,
  ui,
}: {
  step: Extract<Step, { kind: "decision" }>;
  ui: RicoUI;
}) {
  return (
    <div className="flex gap-4 items-start">
      <Gutter label={ui.gutter.choose} />
      <div className="flex-1">
        <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink-mute)] mb-1.5">
          {step.label}
        </div>
        <ul className="space-y-1">
          {step.options.map((o) => {
            const picked = o === step.picked;
            return (
              <li
                key={o}
                className={`flex items-baseline gap-2 text-[14px] leading-snug ${
                  picked
                    ? "text-[var(--ink)]"
                    : "text-[var(--ink-mute)]/70 line-through"
                }`}
              >
                <span
                  className={`font-mono text-[11px] ${
                    picked ? "text-[var(--sun)]" : "text-[var(--ink-mute)]/60"
                  }`}
                >
                  {picked ? "→" : "  "}
                </span>
                <span className={picked ? "italic" : ""}>{o}</span>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

function DiffLine({
  step,
  ui,
}: {
  step: Extract<Step, { kind: "diff" }>;
  ui: RicoUI;
}) {
  return (
    <div className="flex gap-4 items-start">
      <Gutter label={ui.gutter.write} tone="hot" />
      <div className="flex-1 min-w-0">
        <div
          dir="ltr"
          className="font-mono text-[12px] text-[var(--ink-mute)] mb-1"
        >
          {step.file}
        </div>
        <div className="border-s-2 border-[var(--sun)]/60 ps-3">
          {step.added.map((l, i) => (
            <div
              key={i}
              className={`font-display text-[16px] leading-[1.55] ${
                l === "" ? "h-2" : "text-[var(--ink)]"
              }`}
            >
              {l}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DoneLine({
  text,
  suggestions,
}: {
  text: string;
  suggestions?: string[];
}) {
  const { lang } = useLang();
  const dict = useRicoDict();
  return (
    <div className="flex gap-4 items-start pt-2 border-t border-[var(--rule)]/60 mt-2">
      <Gutter label={dict.ui.gutter.rico} tone="hot" />
      <div className="flex-1">
        <p className="text-[16px] leading-relaxed text-[var(--ink)]">
          <Sparkle className="inline-block w-3.5 h-3.5 me-1 -translate-y-[1px] text-[var(--sun)]" />
          {text}
        </p>
        {suggestions && suggestions.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => showPrototypeNotice("forbidden")}
                dir={lang === "ar" ? "rtl" : "ltr"}
                className="group inline-flex items-center gap-1.5 rounded-full border border-[var(--rule)] bg-[var(--card)] px-3 py-1 font-mono text-[11px] text-[var(--ink-soft)] hover:border-[var(--ink)] hover:text-[var(--ink)] transition-colors"
              >
                <span className="text-[var(--sun)] group-hover:translate-x-0.5 transition-transform rtl:-scale-x-100">
                  →
                </span>
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PlanLine({
  items,
  checked,
  ui,
}: {
  items: string[];
  checked: Set<string>;
  ui: RicoUI;
}) {
  const doneCount = items.filter((i) => checked.has(i)).length;
  return (
    <div className="flex gap-4 items-start">
      <Gutter label={ui.gutter.plan} />
      <div className="flex-1 border-s border-[var(--rule)] ps-3">
        <div className="mb-1.5 flex items-baseline gap-2">
          <span
            dir="ltr"
            className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink-mute)]"
          >
            {doneCount} / {items.length}
          </span>
          <span className="h-px flex-1 bg-[var(--rule)]/70" />
        </div>
        <ul className="space-y-1">
          {items.map((it, i) => {
            const done = checked.has(it);
            return (
              <li
                key={it}
                className="flex items-baseline gap-2 text-[14px] leading-snug transition-all"
              >
                <span
                  className={`inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-[3px] border font-mono text-[10px] leading-none transition-colors ${
                    done
                      ? "border-[var(--sun)] bg-[var(--sun)] text-[var(--paper)]"
                      : "border-[var(--rule)] text-transparent"
                  }`}
                >
                  ✓
                </span>
                <span
                  dir="ltr"
                  className={`font-mono text-[10px] uppercase tracking-[0.18em] ${
                    done
                      ? "text-[var(--ink-mute)]/60"
                      : "text-[var(--ink-mute)]"
                  }`}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span
                  className={
                    done
                      ? "text-[var(--ink-mute)]/70 line-through decoration-[var(--ink-mute)]/40"
                      : "text-[var(--ink)]"
                  }
                >
                  {it}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

function CheckLine({ item, ui }: { item: string; ui: RicoUI }) {
  return (
    <div className="flex gap-4 items-baseline -my-2">
      <Gutter label={ui.gutter.check} tone="hot" />
      <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink-mute)]">
        {item}
      </span>
    </div>
  );
}

function ErrorLine({
  step,
  ui,
}: {
  step: Extract<Step, { kind: "error" }>;
  ui: RicoUI;
}) {
  return (
    <div className="flex gap-4 items-start">
      <Gutter label={ui.gutter.fail} tone="hot" />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-[var(--sun)] translate-y-[2px] shrink-0" />
          <span
            dir="ltr"
            className="font-mono text-[13px] text-[var(--ink)]"
          >
            {step.name}
          </span>
          {step.arg && (
            <span
              dir="ltr"
              className="font-mono text-[13px] text-[var(--ink-mute)] truncate"
            >
              ({step.arg})
            </span>
          )}
        </div>
        <pre className="mt-1.5 font-mono text-[12.5px] leading-[1.65] text-[var(--sun)] whitespace-pre-wrap border-s-2 border-[var(--sun)]/60 ps-3">
          ✗ {step.message}
        </pre>
        {step.retryNote && (
          <div className="mt-1.5 flex items-baseline gap-2 text-[13px] italic text-[var(--ink-soft)]">
            <RotateCcw className="w-3 h-3 translate-y-[2px] text-[var(--ink-mute)] rtl:-scale-x-100" />
            {step.retryNote}
          </div>
        )}
      </div>
    </div>
  );
}

function AskLine({
  step,
  answered,
  ui,
}: {
  step: Extract<Step, { kind: "ask" }>;
  answered: boolean;
  ui: RicoUI;
}) {
  const pickedOption = step.options[step.autoPickIndex] ?? step.options[0];
  return (
    <div className="flex gap-4 items-start">
      <Gutter label={ui.gutter.ask} tone="hot" />
      <div className="flex-1">
        <p className="text-[15px] leading-relaxed text-[var(--ink)] mb-2">
          {step.question}
        </p>
        <div className="flex flex-wrap gap-1.5">
          {step.options.map((o, i) => {
            const isPick = i === step.autoPickIndex && answered;
            return (
              <button
                key={o}
                disabled={answered}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[11px] transition-all ${
                  isPick
                    ? "border-[var(--sun)] bg-[var(--sun)]/10 text-[var(--ink)]"
                    : answered
                      ? "border-[var(--rule)] bg-transparent text-[var(--ink-mute)]/60 line-through"
                      : "border-[var(--rule)] bg-[var(--card)] text-[var(--ink-soft)] hover:border-[var(--ink)] hover:text-[var(--ink)]"
                }`}
              >
                {isPick && <span className="text-[var(--sun)]">→</span>}
                {o}
              </button>
            );
          })}
        </div>
        {answered && (
          <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--ink-mute)]">
            {ui.ask.youPrefix} {pickedOption}
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Job match card                                                     */
/* ------------------------------------------------------------------ */

function JobMatchLine({
  step,
  arriving,
  ui,
}: {
  step: Extract<Step, { kind: "jobmatch" }>;
  arriving: boolean;
  ui: RicoUI;
}) {
  return (
    <div className="flex gap-4 items-start">
      <Gutter
        label={ui.gutter.match}
        tone={step.recommended ? "hot" : "mute"}
      />
      <div
        className={`flex-1 min-w-0 rounded-lg border bg-[var(--card)] p-4 transition-all duration-500 ${
          arriving ? "opacity-0 translate-y-1" : "opacity-100 translate-y-0"
        } ${
          step.recommended
            ? "border-[var(--sun)]/70 shadow-[0_0_0_1px_var(--sun)/20,0_16px_32px_-24px_rgba(20,17,13,0.25)]"
            : "border-[var(--rule)]"
        }`}
      >
        {/* header row */}
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2 flex-wrap">
              <span
                dir="ltr"
                className="font-display text-[18px] leading-tight text-[var(--ink)]"
              >
                {step.role}
              </span>
              {step.recommended && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[var(--sun)]/12 border border-[var(--sun)]/60 px-1.5 py-[1px] font-mono text-[9px] uppercase tracking-[0.22em] text-[var(--ink)]">
                  <Sparkle className="w-2.5 h-2.5 text-[var(--sun)]" />
                  {ui.jobMatch.ricoPicks}
                </span>
              )}
              <span
                title={ui.jobMatch.sampleTooltip}
                className="inline-flex items-center rounded-[3px] border border-[var(--sun)]/70 px-1.5 py-[1px] font-mono text-[9px] uppercase tracking-[0.22em] text-[var(--sun)] bg-[var(--sun)]/5"
              >
                {ui.jobMatch.sampleData}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 font-mono text-[11px] text-[var(--ink-mute)]">
              <span
                dir="ltr"
                className="inline-flex items-center gap-1 text-[var(--ink-soft)]"
              >
                <Building2 className="w-3 h-3 translate-y-[1px]" />
                {step.company}
              </span>
              <span className="inline-flex items-center gap-1">
                <MapPin className="w-3 h-3 translate-y-[1px]" />
                {step.city}
              </span>
              <span className="inline-flex items-center gap-1">
                <Wallet className="w-3 h-3 translate-y-[1px]" />
                <span dir="ltr">{step.salary}</span>
              </span>
              <span className="opacity-70">· {step.posted}</span>
            </div>
          </div>
          <ScorePip score={step.score} ui={ui} />
        </div>

        {/* why-fit */}
        <div className="mt-3 border-s-2 border-[var(--sun)]/50 ps-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)] mb-1">
            {ui.jobMatch.whyFits}
          </div>
          <ul className="space-y-1">
            {step.why.map((w) => (
              <li
                key={w}
                className="flex items-baseline gap-2 text-[14px] leading-snug text-[var(--ink)]"
              >
                <span className="font-mono text-[var(--sun)] text-[11px] rtl:-scale-x-100">
                  →
                </span>
                <span>{w}</span>
              </li>
            ))}
          </ul>

          {step.gaps && step.gaps.length > 0 && (
            <>
              <div className="mt-2.5 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)] mb-1">
                {ui.jobMatch.honestGaps}
              </div>
              <ul className="space-y-1">
                {step.gaps.map((g) => (
                  <li
                    key={g}
                    className="flex items-baseline gap-2 text-[13.5px] leading-snug text-[var(--ink-soft)] italic"
                  >
                    <span className="font-mono text-[var(--ink-mute)] text-[11px]">
                      ·
                    </span>
                    <span>{g}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        {/* actions */}
        <div className="mt-3.5 flex items-center gap-2 pt-3 border-t border-[var(--rule)]/60">
          <button
            type="button"
            onClick={() => showPrototypeNotice("forbidden")}
            className="inline-flex items-center gap-1.5 rounded-md bg-[var(--ink)] text-[var(--paper)] px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] hover:bg-[var(--sun)] transition-colors"
          >
            {ui.jobMatch.tailorApply}
          </button>
          <button
            type="button"
            onClick={() => showPrototypeNotice("forbidden")}
            className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink-mute)] hover:text-[var(--ink)] transition-colors"
          >
            {ui.jobMatch.save}
          </button>
          <button
            type="button"
            onClick={() => showPrototypeNotice("forbidden")}
            className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink-mute)] hover:text-[var(--ink)] transition-colors"
          >
            {ui.jobMatch.skip}
          </button>
          <span className="ms-auto font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            {ui.jobMatch.fitLabel}{" "}
            <span dir="ltr">{step.score}%</span>
          </span>
        </div>
      </div>
    </div>
  );
}

function ScorePip({
  score,
  small = false,
  ui,
}: {
  score: number;
  small?: boolean;
  ui: RicoUI;
}) {
  const tier =
    score >= 88 ? "strong" : score >= 78 ? "solid" : "stretch";
  const label =
    tier === "strong"
      ? ui.scorePip.strong
      : tier === "solid"
        ? ui.scorePip.solid
        : ui.scorePip.stretch;
  const tone =
    tier === "strong"
      ? "border-[var(--sun)] text-[var(--ink)] bg-[var(--sun)]/12"
      : tier === "solid"
        ? "border-[var(--ink)]/40 text-[var(--ink)] bg-transparent"
        : "border-[var(--rule)] text-[var(--ink-mute)] bg-transparent";
  const size = small
    ? "text-[10px] px-1.5 py-[1px]"
    : "text-[11px] px-2 py-[2px]";
  return (
    <span
      dir="ltr"
      className={`shrink-0 inline-flex items-baseline gap-1 rounded-full border font-mono uppercase tracking-[0.18em] ${size} ${tone}`}
      title={label}
    >
      <span className="font-display text-[13px] leading-none translate-y-[1px]">
        {score}
      </span>
      <span className="opacity-70">%</span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  CV tailoring diff                                                  */
/* ------------------------------------------------------------------ */

function CvDiffLine({
  step,
  arriving,
  ui,
}: {
  step: Extract<Step, { kind: "cvdiff" }>;
  arriving: boolean;
  ui: RicoUI;
}) {
  const total = 1 + step.bullets.length;
  const revealed = useLineReveal(total, arriving, 700);
  const shown = arriving ? revealed : total;

  // Fake "applied" success state removed for prototype honesty (PR-2).
  // Both action buttons now raise the forbidden notice instead.
  const applied = false;
  const [rejected, setRejected] = useState<Set<number>>(new Set());
  const readyToApply = shown >= total;

  return (
    <div className="flex gap-4 items-start">
      <Gutter
        label={applied ? ui.gutter.wrote : ui.gutter.cv}
        tone={applied ? "mute" : "hot"}
      />
      <div className="flex-1 min-w-0 rounded-lg border border-[var(--rule)] bg-[var(--card)] p-4">
        {/* header */}
        <div className="mb-3 flex items-baseline gap-2 flex-wrap">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            {ui.cvdiff.tailoredFor}
          </span>
          <span
            dir="ltr"
            className="font-display text-[14px] leading-tight text-[var(--ink)]"
          >
            {step.jobRef}
          </span>
          <span className="h-px flex-1 bg-[var(--rule)]/70" />
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            <span dir="ltr">{step.bullets.length + 1}</span>{" "}
            {ui.cvdiff.editsSuffix}
          </span>
        </div>

        <DiffBlock
          label={ui.cvdiff.summaryLabel}
          before={step.summary.before}
          after={step.summary.after}
          why={step.summary.why}
          visible={shown >= 1}
          rejected={rejected.has(0)}
          onToggleReject={() =>
            !applied &&
            setRejected((s) => {
              const n = new Set(s);
              if (n.has(0)) n.delete(0);
              else n.add(0);
              return n;
            })
          }
          applied={applied}
          ui={ui}
        />

        <div className="mt-3 space-y-3">
          {step.bullets.map((b, i) => {
            const idx = i + 1;
            const visible = shown >= idx + 1;
            return (
              <DiffBlock
                key={b.role}
                label={`${ui.cvdiff.bulletPrefix} ${b.role}`}
                before={b.before}
                after={b.after}
                why={b.why}
                visible={visible}
                rejected={rejected.has(idx)}
                onToggleReject={() =>
                  !applied &&
                  setRejected((s) => {
                    const n = new Set(s);
                    if (n.has(idx)) n.delete(idx);
                    else n.add(idx);
                    return n;
                  })
                }
                applied={applied}
                ui={ui}
              />
            );
          })}
        </div>

        <div className="mt-4 flex items-center gap-2 pt-3 border-t border-[var(--rule)]/60">
          <button
            type="button"
            disabled={!readyToApply}
            onClick={() => showPrototypeNotice("forbidden")}
            className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] transition-all ${
              !readyToApply
                ? "bg-[var(--paper-2)] text-[var(--ink-mute)]/60"
                : "bg-[var(--ink)] text-[var(--paper)] hover:bg-[var(--sun)]"
            }`}
          >
            {step.applyLabel}
            {readyToApply && <span aria-hidden>↵</span>}
          </button>
          <button
            type="button"
            onClick={() => showPrototypeNotice("forbidden")}
            className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink-mute)] transition-colors hover:text-[var(--ink)]"
          >
            {ui.cvdiff.keepOriginal}
          </button>
          <span className="ms-auto font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            {ui.cvdiff.willApply(total - rejected.size, total)}
          </span>
        </div>
      </div>
    </div>
  );
}

function DiffBlock({
  label,
  before,
  after,
  why,
  visible,
  rejected,
  onToggleReject,
  applied,
  ui,
}: {
  label: string;
  before: string;
  after: string;
  why: string;
  visible: boolean;
  rejected: boolean;
  onToggleReject: () => void;
  applied: boolean;
  ui: RicoUI;
}) {
  return (
    <div
      className={`transition-opacity duration-500 ${
        visible ? "opacity-100" : "opacity-0"
      }`}
    >
      <div className="mb-1 flex items-baseline gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)] truncate">
          {label}
        </span>
        <span className="h-px flex-1 bg-[var(--rule)]/50" />
        {!applied && visible && (
          <button
            onClick={onToggleReject}
            className={`font-mono text-[10px] uppercase tracking-[0.22em] transition-colors ${
              rejected
                ? "text-[var(--sun)] hover:text-[var(--ink)]"
                : "text-[var(--ink-mute)] hover:text-[var(--ink)]"
            }`}
          >
            {rejected ? ui.cvdiff.include : ui.cvdiff.skip}
          </button>
        )}
        {applied && !rejected && (
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--sun)]">
            {ui.cvdiff.written}
          </span>
        )}
        {applied && rejected && (
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            {ui.cvdiff.skipped}
          </span>
        )}
      </div>

      <div className={rejected ? "opacity-40" : "opacity-100"}>
        {/* before */}
        <div className="flex gap-2 border-s-2 border-[var(--ink-mute)]/40 ps-3 py-0.5">
          <span className="font-mono text-[11px] text-[var(--ink-mute)] shrink-0 select-none translate-y-[3px]">
            −
          </span>
          <p
            dir="ltr"
            className="text-[13.5px] leading-relaxed text-[var(--ink-mute)] line-through decoration-[var(--ink-mute)]/40"
          >
            {before}
          </p>
        </div>
        {/* after */}
        <div className="mt-1 flex gap-2 border-s-2 border-[var(--sun)]/70 ps-3 py-0.5">
          <span className="font-mono text-[11px] text-[var(--sun)] shrink-0 select-none translate-y-[3px]">
            +
          </span>
          <p
            dir="ltr"
            className="text-[14px] leading-relaxed text-[var(--ink)]"
          >
            {after}
          </p>
        </div>
        {/* why */}
        <div className="mt-1.5 ps-3 flex items-baseline gap-2 text-[12.5px] italic text-[var(--ink-soft)]">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--ink-mute)] not-italic shrink-0">
            {ui.cvdiff.why}
          </span>
          <span>{why}</span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Inline form                                                        */
/* ------------------------------------------------------------------ */

function FormLine({
  step,
  committed,
  ui,
}: {
  step: Extract<Step, { kind: "form" }>;
  committed: boolean;
  ui: RicoUI;
}) {
  const revealCount = useLineReveal(step.fields.length, !committed, 550);
  const shown = committed ? step.fields.length : revealCount;

  return (
    <div className="flex gap-4 items-start">
      <Gutter
        label={committed ? ui.form.savedGutter : ui.gutter.form}
        tone={committed ? "mute" : "hot"}
      />
      <div className="flex-1 min-w-0 border-s-2 border-[var(--sun)]/60 ps-3">
        <div className="mb-2 flex items-baseline gap-2">
          <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink-mute)]">
            {step.title}
          </span>
          <span className="h-px flex-1 bg-[var(--rule)]/70" />
          {committed && (
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--sun)]">
              {ui.form.committed}
            </span>
          )}
        </div>

        <div className="space-y-1.5">
          {step.fields.map((f, i) => {
            const visible = i < shown;
            const isFilling = i === shown - 1 && !committed;
            return (
              <div
                key={f.label}
                className={`grid grid-cols-[110px_1fr_auto] items-baseline gap-3 py-1 border-b border-[var(--rule)]/50 transition-opacity duration-300 ${
                  visible ? "opacity-100" : "opacity-0"
                }`}
              >
                <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink-mute)]">
                  {f.label}
                </span>
                <span className="font-display text-[16px] leading-tight text-[var(--ink)]">
                  {visible ? (
                    <>
                      {f.value}
                      {isFilling && (
                        <span className="inline-block w-[7px] h-[0.95em] translate-y-[2px] bg-[var(--ink)] ms-0.5 animate-pulse" />
                      )}
                    </>
                  ) : (
                    <span className="text-[var(--ink-mute)]/40">···</span>
                  )}
                </span>
                <span
                  dir="ltr"
                  className="font-mono text-[9px] uppercase tracking-[0.2em] text-[var(--ink-mute)]"
                >
                  {f.kind ?? "text"}
                </span>
              </div>
            );
          })}
        </div>

        <div className="mt-3 flex items-center gap-2">
          <button
            disabled={committed || shown < step.fields.length}
            className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] transition-all ${
              committed
                ? "bg-transparent text-[var(--ink-mute)] line-through"
                : shown < step.fields.length
                  ? "bg-[var(--paper-2)] text-[var(--ink-mute)]/60"
                  : "bg-[var(--ink)] text-[var(--paper)] hover:bg-[var(--sun)]"
            }`}
          >
            {committed ? ui.form.savedGutter : step.confirm}
            {!committed && shown >= step.fields.length && (
              <span aria-hidden>↵</span>
            )}
          </button>
          <button
            disabled={committed}
            className={`font-mono text-[11px] uppercase tracking-[0.18em] transition-colors ${
              committed
                ? "text-[var(--ink-mute)]/40"
                : "text-[var(--ink-mute)] hover:text-[var(--ink)]"
            }`}
          >
            {ui.form.edit}
          </button>
          <span className="ms-auto font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            {ui.form.subjectPrefix} <span dir="ltr">{step.subject}</span>
          </span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Composer                                                           */
/* ------------------------------------------------------------------ */

function Composer({
  inputRef,
  running,
  pending,
  onStop,
  onRestart,
  onSend,
  ui,
}: {
  inputRef: React.RefObject<HTMLTextAreaElement>;
  running: boolean;
  pending: boolean;
  onStop: () => void;
  onRestart: () => void;
  onSend: (text: string) => void | Promise<void>;
  ui: RicoUI;
}) {
  const [val, setVal] = useState("");
  const canSend = val.trim().length > 0 && !pending;

  function submit() {
    if (!canSend) return;
    const text = val;
    setVal("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    void onSend(text);
  }

  return (
    <div className="sticky bottom-0 z-20 bg-gradient-to-t from-[var(--paper)] via-[var(--paper)]/95 to-[var(--paper)]/0 pt-8 pb-6">
      <div className="mx-auto max-w-[720px] px-6 md:px-8">
        <div className="flex items-end gap-2 border border-[var(--rule)] rounded-2xl bg-[var(--card)] px-3 py-2.5 shadow-[0_1px_0_rgba(20,17,13,0.04),0_20px_40px_-20px_rgba(20,17,13,0.15)] focus-within:border-[var(--sun)] focus-within:ring-1 focus-within:ring-[var(--sun)]/20 transition-colors">
          <span
            aria-hidden
            className="font-mono text-[15px] text-[var(--sun)]/70 select-none pb-1.5"
          >
            /
          </span>
          <button
            aria-label={ui.composer.attachCV}
            className="p-1.5 rounded-md text-[var(--ink-mute)] hover:text-[var(--ink)] hover:bg-[var(--paper-2)] transition-colors"
          >
            <Paperclip className="w-4 h-4" />
          </button>
          <textarea
            ref={inputRef}
            rows={1}
            dir="auto"
            value={val}
            onChange={(e) => {
              setVal(e.target.value);
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 200) + "px";
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={
              pending
                ? ui.composer.placeholderPending
                : running
                  ? ui.composer.placeholderRunning
                  : ui.composer.placeholderIdle
            }
            className="flex-1 resize-none bg-transparent outline-none text-[15px] leading-relaxed text-[var(--ink)] placeholder:text-[var(--ink-mute)]/70 py-1.5"
          />
          {(running || pending) && !canSend ? (
            <button
              onClick={onStop}
              aria-label={ui.composer.stop}
              className="p-2 rounded-md bg-[var(--ink)] text-[var(--paper)] hover:bg-[var(--sun)] transition-colors"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!canSend}
              aria-label={ui.composer.send}
              className="p-2 rounded-md bg-[var(--ink)] text-[var(--paper)] hover:bg-[var(--sun)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="mt-2.5 flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
          <span className="inline-flex items-center gap-1">
            <Command className="w-3 h-3" /> {ui.composer.kCommands}
          </span>
          <span dir="ltr" className="hidden sm:inline">
            {ui.composer.slashHelp}
          </span>
          <button
            onClick={onRestart}
            className="ms-auto text-[var(--ink)] hover:text-[var(--sun)] transition-colors"
          >
            {ui.composer.reset}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Little atoms                                                       */
/* ------------------------------------------------------------------ */

function Dot({ delay }: { delay: number }) {
  return (
    <span
      className="inline-block w-1 h-1 rounded-full bg-[var(--sun)] animate-bounce"
      style={{ animationDelay: `${delay}ms`, animationDuration: "900ms" }}
    />
  );
}

function Cursor({ ui }: { ui: RicoUI }) {
  return (
    <div className="flex gap-4 items-center opacity-60">
      <Gutter label="…" />
      <span className="inline-block w-[7px] h-[16px] bg-[var(--ink)] animate-pulse" />
      <span className="sr-only">{ui.status.working}</span>
    </div>
  );
}

/* typewriter — chars per tick */
function useTyping(text: string, active: boolean, msPerChar: number) {
  const [n, setN] = useState(active ? 0 : text.length);
  useEffect(() => {
    if (!active) {
      setN(text.length);
      return;
    }
    setN(0);
    let i = 0;
    const iv = window.setInterval(() => {
      i += 2;
      setN(Math.min(i, text.length));
      if (i >= text.length) window.clearInterval(iv);
    }, msPerChar);
    return () => window.clearInterval(iv);
  }, [text, active, msPerChar]);
  return useMemo(() => text.slice(0, n), [text, n]);
}

function useLineReveal(total: number, active: boolean, perLineMs: number) {
  const [n, setN] = useState(active ? 0 : total);
  useEffect(() => {
    if (!active) {
      setN(total);
      return;
    }
    setN(0);
    let i = 0;
    const iv = window.setInterval(() => {
      i += 1;
      setN(Math.min(i, total));
      if (i >= total) window.clearInterval(iv);
    }, Math.max(120, perLineMs));
    return () => window.clearInterval(iv);
  }, [total, active, perLineMs]);
  return n;
}

/* ------------------------------------------------------------------ */
/*  Tracker                                                            */
/* ------------------------------------------------------------------ */

function TrackerLine({
  step,
  arriving,
  ui,
}: {
  step: Extract<Step, { kind: "tracker" }>;
  arriving: boolean;
  ui: RicoUI;
}) {
  const revealed = useLineReveal(step.current + 1, arriving, 260);
  const shownUpTo = arriving ? revealed : step.current + 1;

  return (
    <div className="flex gap-4 items-start">
      <Gutter label={ui.gutter.track} tone="hot" />
      <div className="flex-1 min-w-0 rounded-lg border border-[var(--rule)] bg-[var(--card)] p-4">
        {/* header */}
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div
              dir="ltr"
              className="font-display text-[16px] leading-tight text-[var(--ink)] truncate"
            >
              {step.jobRef}
            </div>
            <div className="mt-0.5 font-mono text-[11px] text-[var(--ink-soft)] truncate">
              <Building2 className="inline w-3 h-3 me-1 translate-y-[1px]" />
              <span dir="ltr">{step.company}</span>
              <span className="opacity-60">
                {" "}
                {ui.tracker.viaPrefix} <span dir="ltr">{step.via}</span>
              </span>
            </div>
          </div>
          <span className="shrink-0 inline-flex items-center gap-1 rounded-full border border-[var(--sun)]/60 bg-[var(--sun)]/12 px-2 py-[2px] font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink)]">
            <Check className="w-3 h-3 text-[var(--sun)]" />{" "}
            {ui.tracker.appliedBadge}
          </span>
        </div>

        {/* stage bar */}
        <div className="mt-4">
          <div className="flex items-center gap-[6px]">
            {step.stages.map((s, i) => {
              const filled = i < shownUpTo;
              const isCurrent = i === step.current && filled;
              const isPast = i < step.current && filled;
              const label = ui.tracker.stageNames[s] ?? s;
              return (
                <div key={s} className="flex-1 min-w-0">
                  <div
                    className={`h-[4px] rounded-full transition-colors duration-300 ${
                      isPast
                        ? "bg-[var(--ink)]/60"
                        : isCurrent
                          ? "bg-[var(--sun)]"
                          : "bg-[var(--rule)]"
                    }`}
                  />
                  <div
                    className={`mt-1 font-mono text-[9.5px] uppercase tracking-[0.22em] truncate ${
                      isCurrent
                        ? "text-[var(--ink)]"
                        : isPast
                          ? "text-[var(--ink-soft)]"
                          : "text-[var(--ink-mute)]/60"
                    }`}
                  >
                    {label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* meta grid */}
        <div className="mt-4 grid grid-cols-3 gap-3 pt-3 border-t border-[var(--rule)]/60">
          <MetaCell label={ui.tracker.appliedMeta} value={step.appliedOn} />
          <MetaCell
            label={ui.tracker.nextCheckMeta}
            value={step.nextCheck}
            hot
          />
          <MetaCell
            label={ui.tracker.channelMeta}
            value={step.via.split(" · ")[0] ?? step.via}
          />
        </div>

        {step.note && (
          <div className="mt-3 ps-3 border-s-2 border-[var(--sun)]/60 text-[13.5px] italic text-[var(--ink-soft)] leading-relaxed">
            {step.note}
          </div>
        )}

        <div className="mt-3.5 flex items-center gap-2 pt-3 border-t border-[var(--rule)]/60">
          <button
            type="button"
            onClick={() => showPrototypeNotice("forbidden")}
            className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink)] hover:text-[var(--sun)] transition-colors"
          >
            {ui.tracker.openThread}
          </button>
          <button
            type="button"
            onClick={() => showPrototypeNotice("forbidden")}
            className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink-mute)] hover:text-[var(--ink)] transition-colors"
          >
            {ui.tracker.advanceStage}
          </button>
          <button
            type="button"
            onClick={() => showPrototypeNotice("forbidden")}
            className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink-mute)] hover:text-[var(--ink)] transition-colors"
          >
            {ui.tracker.markRejected}
          </button>
          <span className="ms-auto inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            <CalendarClock className="w-3 h-3" /> {ui.tracker.reminderSet}
          </span>
        </div>
      </div>
    </div>
  );
}

function MetaCell({
  label,
  value,
  hot = false,
}: {
  label: string;
  value: string;
  hot?: boolean;
}) {
  return (
    <div className="min-w-0">
      <div className="font-mono text-[9.5px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
        {label}
      </div>
      <div
        className={`mt-0.5 font-display text-[13.5px] leading-tight truncate ${
          hot ? "text-[var(--ink)]" : "text-[var(--ink-soft)]"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Reminder                                                           */
/* ------------------------------------------------------------------ */

function ReminderLine({
  step,
  arriving,
  ui,
}: {
  step: Extract<Step, { kind: "reminder" }>;
  arriving: boolean;
  ui: RicoUI;
}) {
  const [sent, setSent] = useState(false);
  const [skipped, setSkipped] = useState(false);
  const revealed = useLineReveal(step.draftBody.length, arriving, 380);
  const shown =
    arriving && !sent && !skipped ? revealed : step.draftBody.length;

  return (
    <div className="flex gap-4 items-start">
      <Gutter
        label={sent ? ui.gutter.sent : skipped ? ui.gutter.held : ui.gutter.nudge}
        tone={sent ? "mute" : "hot"}
      />
      <div className="flex-1 min-w-0 rounded-lg border border-dashed border-[var(--sun)]/60 bg-[var(--card)] p-4">
        {/* header */}
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--sun)]">
            <Bell className="w-3 h-3" /> {step.dayLabel}
          </span>
          <span className="h-px flex-1 bg-[var(--rule)]/70" />
          <span
            dir="ltr"
            className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)] truncate"
          >
            {step.jobRef}
          </span>
        </div>

        <p className="mt-2 text-[14px] leading-relaxed text-[var(--ink)]">
          {step.headline}
        </p>

        {/* draft (always LTR — professional English follow-up copy) */}
        <div
          dir="ltr"
          className="mt-3 rounded-md border border-[var(--rule)]/70 bg-[var(--paper)]/60 p-3 text-left"
        >
          <div className="flex items-baseline gap-2 pb-2 mb-2 border-b border-[var(--rule)]/60">
            <span className="font-mono text-[9.5px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
              {ui.reminder.draftLabel}
            </span>
            <span className="font-mono text-[11px] text-[var(--ink-soft)] truncate">
              {step.channel}
            </span>
          </div>
          <div className="font-display text-[14px] leading-tight text-[var(--ink)] mb-2">
            {step.draftSubject}
          </div>
          <div className="space-y-2">
            {step.draftBody.map((p, i) => (
              <p
                key={i}
                className={`text-[13.5px] leading-relaxed whitespace-pre-line transition-opacity duration-300 ${
                  i < shown ? "opacity-100 text-[var(--ink-soft)]" : "opacity-0"
                }`}
              >
                {p}
              </p>
            ))}
          </div>
        </div>

        {/* actions */}
        <div className="mt-3.5 flex items-center gap-2 pt-3 border-t border-[var(--rule)]/60">
          <button
            disabled={sent || skipped}
            onClick={() => setSent(true)}
            className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] transition-all ${
              sent
                ? "bg-transparent text-[var(--ink-mute)] line-through"
                : skipped
                  ? "bg-[var(--paper-2)] text-[var(--ink-mute)]/60"
                  : "bg-[var(--ink)] text-[var(--paper)] hover:bg-[var(--sun)]"
            }`}
          >
            {sent ? ui.reminder.sent : ui.reminder.sendOnDay5}
            {!sent && !skipped && (
              <Send className="w-3 h-3 rtl:-scale-x-100" />
            )}
          </button>
          <button
            disabled={sent || skipped}
            className={`font-mono text-[11px] uppercase tracking-[0.18em] transition-colors ${
              sent || skipped
                ? "text-[var(--ink-mute)]/40"
                : "text-[var(--ink-mute)] hover:text-[var(--ink)]"
            }`}
          >
            {ui.reminder.editDraft}
          </button>
          <button
            disabled={sent || skipped}
            onClick={() => setSkipped(true)}
            className={`font-mono text-[11px] uppercase tracking-[0.18em] transition-colors ${
              sent || skipped
                ? "text-[var(--ink-mute)]/40"
                : "text-[var(--ink-mute)] hover:text-[var(--ink)]"
            }`}
          >
            {ui.reminder.holdCta}
          </button>
          <span className="ms-auto font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            {sent
              ? ui.reminder.queued
              : skipped
                ? ui.reminder.heldReview
                : ui.reminder.autoHold}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Analytics                                                          */
/* ------------------------------------------------------------------ */

function AnalyticsLine({
  step,
  arriving,
  ui,
}: {
  step: Extract<Step, { kind: "analytics" }>;
  arriving: boolean;
  ui: RicoUI;
}) {
  const phases =
    step.funnel.length + step.stageTimes.length + step.insights.length + 1;
  const revealed = useLineReveal(phases, arriving, 260);
  const shown = arriving ? revealed : phases;

  const base = step.funnel[0]?.count ?? 1;
  const maxAvg = Math.max(
    ...step.stageTimes.map((s) => Math.max(s.avgDays, s.benchDays)),
    1,
  );

  let idx = 0;

  return (
    <div className="flex gap-4 items-start">
      <Gutter label={ui.gutter.signal} tone="hot" />
      <div className="flex-1 min-w-0 rounded-lg border border-[var(--rule)] bg-[var(--card)] p-4">
        {/* header */}
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="font-display text-[16px] leading-tight text-[var(--ink)]">
            {step.title}
          </span>
          <span className="h-px flex-1 bg-[var(--rule)]/70" />
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            {step.window}
          </span>
        </div>

        {/* funnel */}
        <div className="mt-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)] mb-2">
            {ui.analytics.conversionFunnel}
          </div>
          <ul className="space-y-1.5">
            {step.funnel.map((f) => {
              const width = Math.max(4, Math.round((f.count / base) * 100));
              const visible = shown > idx++;
              const conv = f.convFromPrev;
              const bench = f.benchmark;
              const delta =
                conv != null && bench != null ? conv - bench : null;
              const tone: "good" | "bad" | "neutral" =
                delta == null
                  ? "neutral"
                  : delta > 0.03
                    ? "good"
                    : delta < -0.03
                      ? "bad"
                      : "neutral";
              const Trend =
                tone === "good"
                  ? TrendingUp
                  : tone === "bad"
                    ? TrendingDown
                    : Minus;
              const toneClass =
                tone === "good"
                  ? "text-[var(--sun)]"
                  : tone === "bad"
                    ? "text-[var(--ink)]"
                    : "text-[var(--ink-mute)]";
              const stageLabel =
                ui.analytics.stageNames[f.stage] ?? f.stage;
              return (
                <li
                  key={f.stage}
                  className={`transition-opacity duration-300 ${
                    visible ? "opacity-100" : "opacity-0"
                  }`}
                >
                  <div className="flex items-baseline gap-2 mb-0.5">
                    <span className="font-mono text-[10.5px] uppercase tracking-[0.2em] text-[var(--ink-soft)] w-[80px] shrink-0 truncate">
                      {stageLabel}
                    </span>
                    <span
                      dir="ltr"
                      className="font-display text-[14px] leading-none text-[var(--ink)]"
                    >
                      {f.count}
                    </span>
                    {conv != null && (
                      <span
                        dir="ltr"
                        className="font-mono text-[10.5px] text-[var(--ink-mute)]"
                      >
                        · {Math.round(conv * 100)}%
                        {bench != null && (
                          <span className="opacity-70">
                            {" "}
                            {ui.analytics.vsBench}{" "}
                            {Math.round(bench * 100)}%
                          </span>
                        )}
                      </span>
                    )}
                    {delta != null && (
                      <span
                        dir="ltr"
                        className={`ms-auto inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.2em] ${toneClass}`}
                      >
                        <Trend className="w-3 h-3" />
                        {delta > 0 ? "+" : ""}
                        {Math.round(delta * 100)}
                        {ui.analytics.ppSuffix}
                      </span>
                    )}
                  </div>
                  <div className="h-[6px] rounded-full bg-[var(--rule)] overflow-hidden">
                    <div
                      className={`h-full transition-[width] duration-500 ${
                        tone === "good" || conv == null
                          ? "bg-[var(--sun)]"
                          : tone === "bad"
                            ? "bg-[var(--ink)]/60"
                            : "bg-[var(--ink)]/40"
                      }`}
                      style={{ width: visible ? `${width}%` : "0%" }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        {/* stage times */}
        <div className="mt-5">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)] mb-2">
            {ui.analytics.stageTime}
          </div>
          <ul className="space-y-2">
            {step.stageTimes.map((s) => {
              const visible = shown > idx++;
              const youW = Math.round((s.avgDays / maxAvg) * 100);
              const benchW = Math.round((s.benchDays / maxAvg) * 100);
              const stageLabel =
                ui.analytics.stageNames[s.stage] ?? s.stage;
              return (
                <li
                  key={s.stage}
                  className={`transition-opacity duration-300 ${
                    visible ? "opacity-100" : "opacity-0"
                  }`}
                >
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="font-mono text-[10.5px] uppercase tracking-[0.2em] text-[var(--ink-soft)] truncate">
                      {stageLabel}
                    </span>
                    {s.slowest && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-[var(--sun)]/60 bg-[var(--sun)]/12 px-1.5 py-[1px] font-mono text-[9px] uppercase tracking-[0.22em] text-[var(--ink)]">
                        <AlertTriangle className="w-2.5 h-2.5 text-[var(--sun)]" />
                        {ui.analytics.bottleneck}
                      </span>
                    )}
                    <span
                      dir="ltr"
                      className="ms-auto font-mono text-[10.5px] text-[var(--ink-mute)]"
                    >
                      <span className="text-[var(--ink)]">
                        {s.avgDays.toFixed(1)}
                        {ui.analytics.daysSuffix}
                      </span>
                      <span className="opacity-70">
                        {" "}
                        {ui.analytics.vsBench} {s.benchDays.toFixed(1)}
                        {ui.analytics.daysSuffix}
                      </span>
                    </span>
                  </div>
                  <div className="space-y-1">
                    <div className="h-[4px] rounded-full bg-[var(--rule)] overflow-hidden">
                      <div
                        className={`h-full transition-[width] duration-500 ${
                          s.slowest ? "bg-[var(--sun)]" : "bg-[var(--ink)]/60"
                        }`}
                        style={{ width: visible ? `${youW}%` : "0%" }}
                      />
                    </div>
                    <div className="h-[3px] rounded-full bg-[var(--rule)]/60 overflow-hidden">
                      <div
                        className="h-full bg-[var(--ink-mute)]/50 transition-[width] duration-500"
                        style={{ width: visible ? `${benchW}%` : "0%" }}
                      />
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="mt-1.5 flex items-center gap-3 font-mono text-[9px] uppercase tracking-[0.22em] text-[var(--ink-mute)]">
            <span className="inline-flex items-center gap-1">
              <span className="inline-block w-2 h-[3px] bg-[var(--sun)]" />{" "}
              {ui.analytics.youLegend}
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="inline-block w-2 h-[3px] bg-[var(--ink-mute)]/50" />{" "}
              {ui.analytics.benchLegend}
            </span>
          </div>
        </div>

        {/* insights */}
        <div className="mt-5">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)] mb-2">
            {ui.analytics.whatMeans}
          </div>
          <ul className="space-y-1.5">
            {step.insights.map((it, i) => {
              const visible = shown > idx++;
              const glyph =
                it.tone === "good" ? "✓" : it.tone === "warn" ? "!" : "×";
              const glyphTone =
                it.tone === "good"
                  ? "text-[var(--sun)]"
                  : it.tone === "warn"
                    ? "text-[var(--ink)]"
                    : "text-[var(--ink-mute)]";
              return (
                <li
                  key={i}
                  className={`flex items-baseline gap-2 text-[13.5px] leading-snug text-[var(--ink-soft)] transition-opacity duration-300 ${
                    visible ? "opacity-100" : "opacity-0"
                  }`}
                >
                  <span
                    className={`font-mono text-[12px] shrink-0 ${glyphTone} translate-y-[1px]`}
                  >
                    {glyph}
                  </span>
                  <span>{it.text}</span>
                </li>
              );
            })}
          </ul>
        </div>

        {/* next moves */}
        <div
          className={`mt-4 pt-3 border-t border-[var(--rule)]/60 transition-opacity duration-300 ${
            shown >= phases ? "opacity-100" : "opacity-0"
          }`}
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--sun)] mb-2">
            {ui.analytics.doNext}
          </div>
          <ol className="space-y-1.5">
            {step.nextMoves.map((m, i) => (
              <li
                key={i}
                className="flex items-baseline gap-2 text-[13.5px] leading-snug text-[var(--ink)]"
              >
                <span
                  dir="ltr"
                  className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--ink-mute)] shrink-0 w-[16px]"
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span>{m}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}
