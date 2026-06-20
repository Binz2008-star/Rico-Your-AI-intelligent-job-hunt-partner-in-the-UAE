/**
 * Rico Command Center — Agentic Conversational UX
 *
 * SCOPE: UI proof only. Mock data. No backend calls. No side effects.
 * Pattern: Plan → Review → Approve → Execute → Receipt (approve step mocked)
 *
 * Mobile-first. Dark/light. Accessible. Keyboard navigable.
 */
'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import type { RicoCard, RicoStatus, PromptChip, ApprovalRecord } from '../components/rico/mock-data';
import {
  MOCK_PROMPT_CHIPS,
  MOCK_CARDS,
  MOCK_QUICK_RESPONSES,
} from '../components/rico/mock-data';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type ApprovalState = {
  open: boolean;
  card: RicoCard | null;
  actionId: string | null;
};

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function generateId(): string {
  return Math.random().toString(36).slice(2, 10);
}

function now(): string {
  return new Date().toISOString();
}

// ---------------------------------------------------------------------------
// Status bar config
// ---------------------------------------------------------------------------
const STATUS_CONFIG: Record<RicoStatus, { label: string; color: string; pulse: boolean }> = {
  idle: { label: 'Rico is ready', color: '#6daa45', pulse: false },
  thinking: { label: 'Thinking…', color: '#d19900', pulse: true },
  proposing: { label: 'Rico has a suggestion', color: '#01696f', pulse: true },
  waiting_approval: { label: 'Waiting for your approval', color: '#da7101', pulse: true },
  executing: { label: 'Executing…', color: '#006494', pulse: true },
  done: { label: 'Done', color: '#6daa45', pulse: false },
  needs_attention: { label: 'Needs your attention', color: '#a13544', pulse: true },
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RicoStatusBar({ status }: { status: RicoStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <div className="rico-status-bar" role="status" aria-live="polite" aria-label={`Rico status: ${cfg.label}`}>
      <span
        className={`rico-status-dot${cfg.pulse ? ' rico-status-dot--pulse' : ''}`}
        style={{ background: cfg.color }}
      />
      <span className="rico-status-label">{cfg.label}</span>
    </div>
  );
}

function PromptChips({
  chips,
  visible,
  onSelect,
}: {
  chips: PromptChip[];
  visible: boolean;
  onSelect: (query: string) => void;
}) {
  return (
    <div className={`rico-chips${visible ? ' rico-chips--visible' : ''}`} role="list" aria-label="Suggested actions">
      {chips.map((chip) => (
        <button
          key={chip.id}
          className="rico-chip"
          role="listitem"
          onClick={() => onSelect(chip.query)}
          aria-label={chip.query}
        >
          <ChipIcon name={chip.icon} />
          {chip.label}
        </button>
      ))}
    </div>
  );
}

function ChipIcon({ name }: { name: string }) {
  const icons: Record<string, React.ReactNode> = {
    briefcase: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <rect x="2" y="7" width="20" height="14" rx="2" />
        <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
      </svg>
    ),
    'help-circle': (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    ),
    'edit-3': (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
      </svg>
    ),
    'bar-chart-2': (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    ),
    zap: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
    list: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <line x1="8" y1="6" x2="21" y2="6" />
        <line x1="8" y1="12" x2="21" y2="12" />
        <line x1="8" y1="18" x2="21" y2="18" />
        <line x1="3" y1="6" x2="3.01" y2="6" />
        <line x1="3" y1="12" x2="3.01" y2="12" />
        <line x1="3" y1="18" x2="3.01" y2="18" />
      </svg>
    ),
    send: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <line x1="22" y1="2" x2="11" y2="13" />
        <polygon points="22 2 15 22 11 13 2 9 22 2" />
      </svg>
    ),
    'file-text': (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    ),
    eye: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
    x: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
      </svg>
    ),
  };
  return <>{icons[name] ?? null}</>;
}

function CardTypeTag({ type }: { type: RicoCard['type'] }) {
  const labels: Record<RicoCard['type'], string> = {
    insight: 'Insight',
    action_proposal: 'Proposal',
    result: 'Result',
    receipt: 'Done',
    warning: 'Attention',
  };
  return <span className={`rico-card-tag rico-card-tag--${type}`}>{labels[type]}</span>;
}

function RicoCardView({
  card,
  onAction,
}: {
  card: RicoCard;
  onAction: (card: RicoCard, actionId: string) => void;
}) {
  const [showReasoning, setShowReasoning] = useState(false);
  const isExecuted = card.status === 'executed' || card.status === 'approved';

  return (
    <article
      className={`rico-card rico-card--${card.type}${isExecuted ? ' rico-card--done' : ''}`}
      aria-label={card.title}
    >
      <header className="rico-card-header">
        <CardTypeTag type={card.type} />
        {card.undo_available && card.status === 'executed' && (
          <span className="rico-undo-badge">↩ Undoable</span>
        )}
      </header>

      <h2 className="rico-card-title">{card.title}</h2>
      <p className="rico-card-body">{card.body}</p>

      {card.data && (
        <dl className="rico-card-data">
          {Object.entries(card.data).map(([k, v]) => (
            <div key={k} className="rico-card-data-row">
              <dt>{k.replace(/_/g, ' ')}</dt>
              <dd>{String(v)}</dd>
            </div>
          ))}
        </dl>
      )}

      {card.reasoning && (
        <div className="rico-reasoning">
          <button
            className="rico-reasoning-toggle"
            onClick={() => setShowReasoning((s) => !s)}
            aria-expanded={showReasoning}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            {showReasoning ? 'Hide' : 'Why did Rico suggest this?'}
          </button>
          {showReasoning && (
            <p className="rico-reasoning-body">{card.reasoning}</p>
          )}
        </div>
      )}

      {!isExecuted && card.actions.length > 0 && (
        <footer className="rico-card-actions">
          {card.actions.map((action) => (
            <button
              key={action.id}
              className={`rico-btn rico-btn--${action.variant}`}
              onClick={() => onAction(card, action.id)}
              aria-label={action.requires_approval
                ? `${action.label} — requires your approval`
                : action.label}
            >
              {action.icon && <ChipIcon name={action.icon} />}
              {action.label}
              {action.requires_approval && (
                <span className="rico-approval-badge" aria-hidden="true">•</span>
              )}
            </button>
          ))}
        </footer>
      )}

      {isExecuted && (
        <footer className="rico-card-actions">
          {card.actions.map((action) => (
            <button
              key={action.id}
              className="rico-btn rico-btn--ghost"
              onClick={() => onAction(card, action.id)}
            >
              {action.icon && <ChipIcon name={action.icon} />}
              {action.label}
            </button>
          ))}
        </footer>
      )}
    </article>
  );
}

function ApprovalSheet({
  state,
  onApprove,
  onReject,
  onClose,
}: {
  state: ApprovalState;
  onApprove: () => void;
  onReject: () => void;
  onClose: () => void;
}) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const card = state.card;
  const action = card?.actions.find((a) => a.id === state.actionId);

  useEffect(() => {
    if (state.open) {
      sheetRef.current?.focus();
      const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
      document.addEventListener('keydown', handler);
      return () => document.removeEventListener('keydown', handler);
    }
  }, [state.open, onClose]);

  if (!state.open || !card || !action) return null;

  return (
    <div className="rico-approval-overlay" role="dialog" aria-modal="true" aria-label="Approve action">
      <div className="rico-approval-sheet" ref={sheetRef} tabIndex={-1}>
        <div className="rico-approval-handle" aria-hidden="true" />
        <h3 className="rico-approval-title">Approve this action?</h3>

        <dl className="rico-approval-details">
          <div className="rico-approval-row">
            <dt>Action</dt>
            <dd>{action.label}</dd>
          </div>
          {action.target_system && (
            <div className="rico-approval-row">
              <dt>System</dt>
              <dd>{action.target_system}</dd>
            </div>
          )}
          {action.expected_effect && (
            <div className="rico-approval-row">
              <dt>What happens</dt>
              <dd>{action.expected_effect}</dd>
            </div>
          )}
          <div className="rico-approval-row">
            <dt>Risk level</dt>
            <dd className={`rico-risk--${action.risk_class}`}>{action.risk_class}</dd>
          </div>
          <div className="rico-approval-row">
            <dt>Undoable</dt>
            <dd>{card.undo_available ? 'Yes' : 'No'}</dd>
          </div>
        </dl>

        <div className="rico-approval-actions">
          <button className="rico-btn rico-btn--primary" onClick={onApprove}>
            Approve
          </button>
          <button className="rico-btn rico-btn--ghost" onClick={onReject}>
            Reject
          </button>
        </div>

        <p className="rico-approval-note">
          This approval is logged with a timestamp and your user ID.
        </p>
      </div>
    </div>
  );
}

function ThinkingSkeleton() {
  return (
    <div className="rico-thinking" aria-label="Rico is thinking" role="status">
      <div className="rico-thinking-bar" style={{ width: '70%' }} />
      <div className="rico-thinking-bar" style={{ width: '50%' }} />
      <div className="rico-thinking-bar" style={{ width: '85%' }} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
export default function RicoCommandCenter() {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<RicoStatus>('idle');
  const [cards, setCards] = useState<RicoCard[]>([]);
  const [approval, setApproval] = useState<ApprovalState>({ open: false, card: null, actionId: null });
  const [approvalLog, setApprovalLog] = useState<ApprovalRecord[]>([]);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  // Theme init from system preference (no localStorage — sandbox constraint)
  useEffect(() => {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    setTheme(prefersDark ? 'dark' : 'light');
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'));
  }, []);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' });
    }, 100);
  }, []);

  const handleSubmit = useCallback(async () => {
    const q = query.trim();
    if (!q || status === 'thinking') return;

    setStatus('thinking');
    setQuery('');
    scrollToBottom();

    // Simulate Rico thinking delay
    await new Promise((r) => setTimeout(r, 1400));

    const response = MOCK_QUICK_RESPONSES[q] ?? [MOCK_CARDS[Math.floor(Math.random() * MOCK_CARDS.length)]];
    const freshCards = response.map((c) => ({ ...c, id: `${c.id}-${generateId()}`, status: 'pending' as const, created_at: now() }));

    setCards((prev) => [...prev, ...freshCards]);
    setStatus(freshCards.some((c) => c.type === 'action_proposal') ? 'proposing' : 'done');
    scrollToBottom();
  }, [query, status, scrollToBottom]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  const handleAction = useCallback((card: RicoCard, actionId: string) => {
    const action = card.actions.find((a) => a.id === actionId);
    if (!action) return;

    if (action.requires_approval) {
      setStatus('waiting_approval');
      setApproval({ open: true, card, actionId });
    } else {
      // Safe action — execute immediately (mock)
      setCards((prev) =>
        prev.map((c) => (c.id === card.id ? { ...c, status: 'executed' } : c))
      );
      setStatus('done');
    }
  }, []);

  const handleApprove = useCallback(() => {
    if (!approval.card || !approval.actionId) return;

    const record: ApprovalRecord = {
      action_id: approval.actionId,
      actor_user_id: 'mock-user-001',
      card_id: approval.card.id,
      approved_at: now(),
      risk_class: approval.card.risk_class,
      target_system: approval.card.actions.find((a) => a.id === approval.actionId)?.target_system ?? 'unknown',
      expected_effect: approval.card.actions.find((a) => a.id === approval.actionId)?.expected_effect ?? '',
      undo_available: approval.card.undo_available,
      idempotency_key: generateId(),
    };

    setApprovalLog((prev) => [...prev, record]);
    setCards((prev) =>
      prev.map((c) => (c.id === approval.card!.id ? { ...c, status: 'approved' } : c))
    );
    setApproval({ open: false, card: null, actionId: null });
    setStatus('executing');

    // Simulate execution
    setTimeout(() => setStatus('done'), 1800);
  }, [approval]);

  const handleReject = useCallback(() => {
    setCards((prev) =>
      prev.map((c) => (c.id === approval.card?.id ? { ...c, status: 'rejected' } : c))
    );
    setApproval({ open: false, card: null, actionId: null });
    setStatus('idle');
  }, [approval]);

  const chipsVisible = query.length === 0 && status === 'idle';

  return (
    <div className="rico-workspace" data-theme={theme}>
      {/* Skip link for accessibility */}
      <a href="#rico-thread" className="sr-only focus-visible">Skip to conversation</a>

      {/* Header */}
      <header className="rico-header">
        <div className="rico-logo" aria-label="Rico AI Career Agent">
          <svg width="28" height="28" viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <rect width="32" height="32" rx="8" fill="var(--color-primary)" />
            <path d="M10 22V10h6a4 4 0 0 1 0 8h-2l4 4" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="22" cy="22" r="2" fill="white" />
          </svg>
          <span className="rico-logo-text">Rico</span>
          <span className="rico-logo-badge">Beta</span>
        </div>

        <div className="rico-header-right">
          <RicoStatusBar status={status} />
          <button
            className="rico-theme-toggle"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <circle cx="12" cy="12" r="5" />
                <line x1="12" y1="1" x2="12" y2="3" />
                <line x1="12" y1="21" x2="12" y2="23" />
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                <line x1="1" y1="12" x2="3" y2="12" />
                <line x1="21" y1="12" x2="23" y2="12" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            )}
          </button>
        </div>
      </header>

      {/* Conversation thread */}
      <main id="rico-thread" className="rico-thread" ref={threadRef}>
        {cards.length === 0 && status === 'idle' && (
          <div className="rico-empty">
            <div className="rico-empty-icon" aria-hidden="true">
              <svg width="40" height="40" viewBox="0 0 32 32" fill="none">
                <rect width="32" height="32" rx="8" fill="var(--color-primary-highlight)" />
                <path d="M10 22V10h6a4 4 0 0 1 0 8h-2l4 4" stroke="var(--color-primary)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="22" cy="22" r="2" fill="var(--color-primary)" />
              </svg>
            </div>
            <h1 className="rico-empty-title">Ask Rico anything about your job search</h1>
            <p className="rico-empty-body">
              Rico analyses your CV, tracks your applications, and suggests the right action at the right time — with your approval before anything is sent.
            </p>
          </div>
        )}

        {cards.map((card) => (
          <RicoCardView key={card.id} card={card} onAction={handleAction} />
        ))}

        {status === 'thinking' && <ThinkingSkeleton />}
        {status === 'executing' && (
          <div className="rico-executing" role="status" aria-live="polite">
            <span className="rico-executing-dot" />
            Executing approved action…
          </div>
        )}

        {approvalLog.length > 0 && (
          <details className="rico-audit-drawer">
            <summary className="rico-audit-toggle">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              Approval log ({approvalLog.length})
            </summary>
            <ul className="rico-audit-list" role="list">
              {approvalLog.map((rec) => (
                <li key={rec.idempotency_key} className="rico-audit-entry">
                  <span className="rico-audit-action">{rec.action_id}</span>
                  <span className="rico-audit-time">{new Date(rec.approved_at).toLocaleTimeString()}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </main>

      {/* Ask box */}
      <footer className="rico-input-area">
        <PromptChips chips={MOCK_PROMPT_CHIPS} visible={chipsVisible} onSelect={(q) => { setQuery(q); inputRef.current?.focus(); }} />

        <div className="rico-input-row">
          <label htmlFor="rico-ask" className="sr-only">Ask Rico</label>
          <textarea
            id="rico-ask"
            ref={inputRef}
            className="rico-ask-box"
            rows={1}
            placeholder="Ask Rico anything…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={status === 'thinking' || status === 'executing' || status === 'waiting_approval'}
            aria-label="Ask Rico a question about your job search"
          />
          <button
            className="rico-send-btn"
            onClick={handleSubmit}
            disabled={!query.trim() || status === 'thinking' || status === 'executing' || status === 'waiting_approval'}
            aria-label="Send question to Rico"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
        <p className="rico-disclaimer">
          Rico is in semi-autonomous mode — it proposes, you approve.
        </p>
      </footer>

      {/* Approval sheet */}
      <ApprovalSheet
        state={approval}
        onApprove={handleApprove}
        onReject={handleReject}
        onClose={() => { setApproval({ open: false, card: null, actionId: null }); setStatus('idle'); }}
      />

      <style>{STYLES}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles — inlined for portability. Move to globals.css / CSS module in prod.
// ---------------------------------------------------------------------------
const STYLES = `
/* ---- Design tokens ---- */
[data-theme='light'] {
  --color-bg: #f7f6f2;
  --color-surface: #f9f8f5;
  --color-surface-2: #fbfbf9;
  --color-surface-offset: #f3f0ec;
  --color-border: oklch(from #28251d l c h / 0.1);
  --color-text: #28251d;
  --color-text-muted: #7a7974;
  --color-text-faint: #bab9b4;
  --color-primary: #01696f;
  --color-primary-hover: #0c4e54;
  --color-primary-highlight: #cedcd8;
  --color-warning: #964219;
  --color-error: #a12c7b;
  --color-success: #437a22;
  --color-shadow: oklch(0.2 0.01 80 / 0.08);
  --font-body: 'Inter', system-ui, sans-serif;
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;
  --radius-full: 9999px;
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
}
[data-theme='dark'] {
  --color-bg: #171614;
  --color-surface: #1c1b19;
  --color-surface-2: #201f1d;
  --color-surface-offset: #22211f;
  --color-border: oklch(from #cdccca l c h / 0.1);
  --color-text: #cdccca;
  --color-text-muted: #797876;
  --color-text-faint: #5a5957;
  --color-primary: #4f98a3;
  --color-primary-hover: #227f8b;
  --color-primary-highlight: #313b3b;
  --color-warning: #bb653b;
  --color-error: #d163a7;
  --color-success: #6daa45;
  --color-shadow: oklch(0 0 0 / 0.35);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
body { font-family: var(--font-body); background: var(--color-bg); color: var(--color-text); }
.sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; }
button { cursor: pointer; background: none; border: none; font: inherit; color: inherit; }

/* ---- Workspace layout ---- */
.rico-workspace {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  max-width: 720px;
  margin: 0 auto;
  background: var(--color-bg);
  position: relative;
  overflow: hidden;
}

/* ---- Header ---- */
.rico-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
  flex-shrink: 0;
  gap: var(--space-4);
}
.rico-logo { display: flex; align-items: center; gap: var(--space-2); }
.rico-logo-text { font-weight: 700; font-size: 1.05rem; letter-spacing: -0.02em; }
.rico-logo-badge {
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: var(--radius-full);
  background: var(--color-primary-highlight);
  color: var(--color-primary);
}
.rico-header-right { display: flex; align-items: center; gap: var(--space-3); }
.rico-theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  transition: background 160ms ease, color 160ms ease;
}
.rico-theme-toggle:hover { background: var(--color-surface-offset); color: var(--color-text); }

/* ---- Status bar ---- */
.rico-status-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 0.78rem;
  color: var(--color-text-muted);
}
.rico-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 300ms ease;
}
.rico-status-dot--pulse {
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}
.rico-status-label { white-space: nowrap; }

/* ---- Thread ---- */
.rico-thread {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  scroll-behavior: smooth;
}

/* ---- Empty state ---- */
.rico-empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-8) 0;
  max-width: 480px;
}
.rico-empty-icon { margin-bottom: var(--space-2); }
.rico-empty-title {
  font-size: clamp(1.15rem, 1rem + 1vw, 1.4rem);
  font-weight: 700;
  line-height: 1.3;
  color: var(--color-text);
  letter-spacing: -0.02em;
}
.rico-empty-body { font-size: 0.9rem; color: var(--color-text-muted); line-height: 1.6; max-width: 52ch; }

/* ---- Cards ---- */
@keyframes card-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.rico-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  animation: card-in 220ms cubic-bezier(0.16, 1, 0.3, 1) both;
  transition: opacity 300ms ease;
}
.rico-card--done { opacity: 0.7; }
.rico-card--receipt { background: color-mix(in oklch, var(--color-success) 6%, var(--color-surface)); }
.rico-card--warning { background: color-mix(in oklch, var(--color-warning) 6%, var(--color-surface)); }
.rico-card--action_proposal { background: color-mix(in oklch, var(--color-primary) 5%, var(--color-surface)); }

.rico-card-header { display: flex; align-items: center; gap: var(--space-2); }
.rico-card-tag {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-surface-offset);
  color: var(--color-text-muted);
}
.rico-card-tag--action_proposal { background: var(--color-primary-highlight); color: var(--color-primary); }
.rico-card-tag--receipt { background: color-mix(in oklch, var(--color-success) 18%, var(--color-surface)); color: var(--color-success); }
.rico-card-tag--warning { background: color-mix(in oklch, var(--color-warning) 18%, var(--color-surface)); color: var(--color-warning); }
.rico-undo-badge {
  font-size: 0.68rem;
  color: var(--color-text-faint);
  margin-left: auto;
}

.rico-card-title {
  font-size: clamp(0.95rem, 0.9rem + 0.3vw, 1.05rem);
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: -0.01em;
  color: var(--color-text);
}
.rico-card-body { font-size: 0.88rem; color: var(--color-text-muted); line-height: 1.65; max-width: 62ch; }

.rico-card-data {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-1) var(--space-4);
  background: var(--color-surface-2);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  font-size: 0.78rem;
}
.rico-card-data-row { display: contents; }
.rico-card-data dt { color: var(--color-text-faint); text-transform: capitalize; }
.rico-card-data dd { color: var(--color-text); font-weight: 600; font-variant-numeric: tabular-nums; }

/* Reasoning */
.rico-reasoning { margin-top: var(--space-1); }
.rico-reasoning-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: 0.75rem;
  color: var(--color-text-faint);
  padding: 0;
  transition: color 160ms ease;
}
.rico-reasoning-toggle:hover { color: var(--color-primary); }
.rico-reasoning-body {
  margin-top: var(--space-2);
  font-size: 0.8rem;
  color: var(--color-text-muted);
  line-height: 1.6;
  padding: var(--space-3);
  background: var(--color-surface-2);
  border-radius: var(--radius-md);
  border-left: 2px solid var(--color-primary-highlight);
}

/* Card actions */
.rico-card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-1);
}

/* ---- Buttons ---- */
.rico-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px 14px;
  border-radius: var(--radius-md);
  font-size: 0.83rem;
  font-weight: 600;
  min-height: 36px;
  transition: background 160ms ease, color 160ms ease, transform 80ms ease, box-shadow 160ms ease;
  white-space: nowrap;
}
.rico-btn:active { transform: scale(0.97); }
.rico-btn--primary {
  background: var(--color-primary);
  color: #fff;
}
.rico-btn--primary:hover { background: var(--color-primary-hover); }
.rico-btn--secondary {
  background: var(--color-surface-offset);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}
.rico-btn--secondary:hover { background: var(--color-surface-2); }
.rico-btn--ghost {
  background: transparent;
  color: var(--color-text-muted);
}
.rico-btn--ghost:hover { background: var(--color-surface-offset); color: var(--color-text); }
.rico-btn--danger { background: var(--color-error); color: #fff; }
.rico-btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
.rico-approval-badge {
  width: 6px;
  height: 6px;
  background: var(--color-warning);
  border-radius: 50%;
  display: inline-block;
}

/* ---- Thinking skeleton ---- */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
.rico-thinking {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-5);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  animation: card-in 220ms ease both;
}
.rico-thinking-bar {
  height: 12px;
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, var(--color-surface-offset) 25%, var(--color-surface-2) 50%, var(--color-surface-offset) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

/* ---- Executing ---- */
.rico-executing {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 0.82rem;
  color: var(--color-text-muted);
  padding: var(--space-3) var(--space-4);
}
.rico-executing-dot {
  width: 8px;
  height: 8px;
  background: var(--color-primary);
  border-radius: 50%;
  animation: pulse 1s ease infinite;
}

/* ---- Prompt chips ---- */
.rico-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: 0 0 var(--space-3);
  max-height: 0;
  overflow: hidden;
  opacity: 0;
  transition: max-height 280ms cubic-bezier(0.16,1,0.3,1), opacity 200ms ease;
}
.rico-chips--visible { max-height: 120px; opacity: 1; }
.rico-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 7px 12px;
  border-radius: var(--radius-full);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  font-size: 0.78rem;
  color: var(--color-text-muted);
  font-weight: 500;
  transition: background 160ms ease, color 160ms ease, border-color 160ms ease;
  min-height: 36px;
}
.rico-chip:hover { background: var(--color-surface-offset); color: var(--color-text); border-color: var(--color-primary); }
.rico-chip:active { transform: scale(0.97); }

/* ---- Input area ---- */
.rico-input-area {
  padding: var(--space-3) var(--space-4) var(--space-4);
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
  flex-shrink: 0;
}
.rico-input-row {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
}
.rico-ask-box {
  flex: 1;
  resize: none;
  background: var(--color-surface-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 10px 14px;
  font-size: 0.92rem;
  color: var(--color-text);
  line-height: 1.5;
  min-height: 44px;
  max-height: 120px;
  transition: border-color 160ms ease, box-shadow 160ms ease;
  font-family: var(--font-body);
  overflow-y: auto;
}
.rico-ask-box::placeholder { color: var(--color-text-faint); }
.rico-ask-box:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--color-primary) 15%, transparent);
}
.rico-ask-box:disabled { opacity: 0.5; cursor: not-allowed; }
.rico-send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  flex-shrink: 0;
  transition: background 160ms ease, transform 80ms ease;
}
.rico-send-btn:hover { background: var(--color-primary-hover); }
.rico-send-btn:active { transform: scale(0.94); }
.rico-send-btn:disabled { opacity: 0.35; cursor: not-allowed; transform: none; }
.rico-disclaimer {
  font-size: 0.7rem;
  color: var(--color-text-faint);
  text-align: center;
  margin-top: var(--space-2);
}

/* ---- Approval sheet ---- */
.rico-approval-overlay {
  position: fixed;
  inset: 0;
  background: oklch(0 0 0 / 0.5);
  display: flex;
  align-items: flex-end;
  z-index: 100;
  animation: fade-in 160ms ease;
}
@keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
.rico-approval-sheet {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  background: var(--color-surface);
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  padding: var(--space-5) var(--space-6) var(--space-8);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  animation: sheet-up 240ms cubic-bezier(0.16,1,0.3,1);
}
@keyframes sheet-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
.rico-approval-handle {
  width: 36px;
  height: 4px;
  border-radius: var(--radius-full);
  background: var(--color-border);
  margin: 0 auto var(--space-2);
}
.rico-approval-title { font-size: 1rem; font-weight: 700; letter-spacing: -0.01em; }
.rico-approval-details {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  background: var(--color-surface-2);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
}
.rico-approval-row { display: flex; justify-content: space-between; gap: var(--space-4); font-size: 0.85rem; }
.rico-approval-row dt { color: var(--color-text-muted); flex-shrink: 0; }
.rico-approval-row dd { color: var(--color-text); font-weight: 600; text-align: right; }
.rico-risk--safe { color: var(--color-success); }
.rico-risk--moderate { color: var(--color-warning); }
.rico-risk--destructive { color: var(--color-error); }
.rico-approval-actions { display: flex; gap: var(--space-3); }
.rico-approval-actions .rico-btn--primary { flex: 1; justify-content: center; padding: 12px; font-size: 0.9rem; }
.rico-approval-actions .rico-btn--ghost { flex: 0 0 auto; }
.rico-approval-note { font-size: 0.72rem; color: var(--color-text-faint); text-align: center; }

/* ---- Audit drawer ---- */
.rico-audit-drawer {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  overflow: hidden;
}
.rico-audit-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  font-size: 0.78rem;
  color: var(--color-text-muted);
  cursor: pointer;
  list-style: none;
  font-weight: 600;
  transition: background 160ms ease;
}
.rico-audit-toggle:hover { background: var(--color-surface-offset); }
.rico-audit-list { padding: var(--space-1) var(--space-4) var(--space-3); }
.rico-audit-entry {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--color-text-muted);
  padding: var(--space-1) 0;
  border-top: 1px solid var(--color-border);
}
.rico-audit-action { font-weight: 500; color: var(--color-text); }
.rico-audit-time { color: var(--color-text-faint); font-variant-numeric: tabular-nums; }

/* ---- Mobile ---- */
@media (max-width: 480px) {
  .rico-card { padding: var(--space-4); border-radius: var(--radius-lg); }
  .rico-header { padding: var(--space-2) var(--space-3); }
  .rico-status-label { display: none; }
  .rico-thread { padding: var(--space-4) var(--space-3); }
  .rico-input-area { padding: var(--space-2) var(--space-3) var(--space-4); }
  .rico-approval-sheet { padding: var(--space-4) var(--space-4) var(--space-6); }
  .rico-empty { padding: var(--space-6) 0; }
}

/* Focus ring */
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
`;
