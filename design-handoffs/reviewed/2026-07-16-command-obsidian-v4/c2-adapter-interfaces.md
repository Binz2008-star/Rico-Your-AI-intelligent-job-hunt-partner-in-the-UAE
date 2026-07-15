# C2 — real Command event/presentation adapter: interface contracts

Owner directive 2026-07-16 (verified against the published Lovable `/rico`
source): the canonical experience is an **interaction grammar** (YOU · THINK ·
PLAN · RUN/TOOL · CHECK · RICO · MATCH · ASK · FORM · DIFF · TRACK · REMINDER ·
ANALYTICS · DONE) with progressive reveal, auto-follow, live status, and a
session-derived rail — but the Lovable project is a scripted prototype
(seeded jobs, static sessions, prototype notices, AI Gateway, localStorage).
**Target = Lovable interaction choreography + Rico's real production APIs,
state and actions.** Nothing below invents state; every step kind is derivable
from data structures that already exist in `app/command/page.tsx` today.

## Files (C2 slice — new presentation layer; zero handler changes)

```text
apps/web/components/command/CommandEventAdapter.ts    — pure, unit-testable mapping
apps/web/components/command/CommandTranscript.tsx     — steps renderer (role=log, auto-follow)
apps/web/components/command/CommandTranscriptStep.tsx — one step: gutter + presentation
apps/web/components/command/CommandConversationRail.tsx — shipped in C1 (unchanged)
```

`CommandEventAdapter.ts` imports **types only** — never handlers, never fetch.
All interactivity flows back to CommandPage's existing handlers through typed
callbacks on `CommandTranscript`.

## Adapter input — existing page truth, verbatim

```ts
/** Everything the adapter may read. All fields already exist in CommandPage. */
export interface CommandTruth {
    messages: Message[];                       // page's Message[] — unchanged shape
    thinking: boolean;                         // page state
    operationState: { state: OperationStateKind; message: string } | null; // pickOperationState()
    audience: "checking" | "public" | "authenticated";
}
```

## Adapter output — canonical transcript steps (discriminated union)

```ts
export type TranscriptStep =
    /* user Message → YOU */
    | { kind: "you"; id: string; text: string }
    /* thinking=true (no tokens yet) → safe WORKING state — NOT model reasoning */
    | { kind: "working"; id: string; label: string }
    /* operationState → RUN / operational step (safe labels: "Searching matching
       roles", "Reading your CV", "Scoring results" — from the existing
       pickOperationState taxonomy; never fabricated tool names) */
    | { kind: "run"; id: string; label: string; live: boolean }
    /* SSE tokens → streaming RICO; completed response → RICO (final) */
    | { kind: "rico"; id: string; text: string; streaming: boolean;
        /* options / next_actions → real actionable suggestions */
        suggestions: RealSuggestion[] }
    /* isError turns (timeout/network/generic) → FAIL + real Retry */
    | { kind: "fail"; id: string; message: string; retryText: string | null }
    /* agentic_ui.progress → PLAN / CHECK rows (only when the API sent them) */
    | { kind: "plan"; id: string; items: { label: string; done: boolean }[] }
    /* agentic_ui.actions → ASK / action controls (real RicoChatAction[]) */
    | { kind: "ask"; id: string; prompt: string; actions: RicoChatAction[];
        dismissed: boolean }
    /* agentic_ui.permission_request → approval checkpoint */
    | { kind: "permission"; id: string; request: RicoPermissionRequest;
        dismissed: boolean }
    /* agentic_ui.proposed_changes → DIFF / review card */
    | { kind: "diff"; id: string; proposal: RicoProposedChange; dismissed: boolean }
    /* attachment_analysis → document intelligence */
    | { kind: "docintel"; id: string; analysis: RicoAttachmentAnalysis }
    /* type=profile_preview → FORM (CV draft review + confirm/edit) */
    | { kind: "form"; id: string; preview: ProfilePreview; filename: string;
        extractionQuality?: string; docType?: string; uploadId?: string | null }
    /* matches → MATCH (one step per job; card keeps verification + fallbacks) */
    | { kind: "match"; id: string; match: JobMatch; caption?: MatchCaption }
    /* applications / follow_up_needed → TRACK / pipeline */
    | { kind: "track"; id: string; applications: ApplicationEntry[];
        followUps: ApplicationEntry[] }
    /* profile_gaps → profile signal */
    | { kind: "signal"; id: string; gaps: string[] };

export interface RealSuggestion { label: string; message: string; action?: string }
export interface MatchCaption { query?: string; resultCount?: number;
    broadened?: boolean; stale?: boolean; rateLimitNotice?: string }
```

Explicitly **absent** step kinds until real state exists to back them:
scripted THINK narration, fabricated TOOL names/arguments, REMINDER and
ANALYTICS (no production source yet — they join the grammar only when a real
API supplies them; tracked as capability gaps, like multi-session history).

## Adapter functions (pure — the C2 unit-test surface)

```ts
/** Message[] + live state → ordered canonical steps. Deterministic, no I/O. */
export function toTranscriptSteps(truth: CommandTruth, t: Translator): TranscriptStep[];

/** Top-bar status from real state only. */
export function deriveStatus(truth: CommandTruth):
    { key: "ready" | "working" | "replying"; busy: boolean };

/** Safe RUN label from the existing operation-state taxonomy. */
export function runLabelFor(op: CommandTruth["operationState"], t: Translator): string;
```

## Renderer contracts

```ts
export function CommandTranscript(props: {
    steps: TranscriptStep[];
    /* auto-follow: pin-to-bottom with the existing 96px threshold behavior */
    containerRef: React.RefObject<HTMLDivElement>;
    callbacks: TranscriptCallbacks;   // existing page handlers, passed through
}): JSX.Element;

/** Every interactive element maps to an EXISTING CommandPage handler —
 *  no new mutations, no duplicated API calls, no decorative dead buttons. */
export interface TranscriptCallbacks {
    onSendPrompt(prompt: string, label?: string): void;        // sendMessage
    onRetry(retryText: string): void;                          // sendMessage(retryText)
    onCopy(id: string, text: string): void;                    // handleCopyMessage
    onActionChip(m: MessageRef, action: RicoChatAction): void; // handleChatAction (execute/open_drawer/send)
    onPermissionDecision(m: MessageRef, approve: boolean): void; // executePermissionAction path
    onProposedApply(m: MessageRef): void;                      // submitAction/updateProfile path
    onProposedDismiss(m: MessageRef): void;                    // existing dismiss flags
    onProfileConfirm(preview: ProfilePreview, filename: string,
        id: number, docType?: string, uploadId?: string | null): void; // confirmCVProfile
    onProfileEdit(id: number, preview: ProfilePreview): void;  // existing edit-before-confirm flow
    onJobAction(prompt: string): void;                         // existing apply/save/fallback prompt path
}
```

`CommandTranscriptStep` renders one step: canonical mono gutter label
(YOU/RUN/RICO/FAIL/ASK/FORM/DIFF/MATCH/TRACK/…, lime for hot states), the
Obsidian presentation, and wires only the callbacks above. Existing components
(JobMatchCard, JobFallbackActions, CVDraftCard, PermissionRequestCard,
ProposedChangeCard, AttachmentAnalysisCard, RicoMarkdownContent) are reused
inside steps — restyled, never re-implemented.

## C2 acceptance

- Adapter unit tests: every mapping row above, including "no agentic_ui → no
  plan/ask/permission/diff steps" (anti-fabrication tests).
- The C1 no-regression suite passes unchanged (same handlers, same flows).
- Streaming/stop/retry re-verified through the new transcript renderer.
- No new fetch call sites in the diff (`git diff` grep gate: no `fetch(`,
  no new `lib/api` mutation imports in presentation files).
