/**
 * BUG-11 regression: duplicate quick-reply buttons must not render when the
 * backend mirrors options into agentic_ui.actions (audit 1-A / _inject_option_buttons).
 *
 * Root cause: OptionButtons (renders m.options) and ChatActionsRow (renders
 * m.agentic_ui.actions) were both rendered unconditionally. The backend's
 * _inject_option_buttons copies options into agentic_ui.actions as chat_continue
 * buttons, so both components rendered the same A/B/C/D buttons.
 *
 * Fix: OptionButtons is suppressed when agentic_ui.actions is non-empty.
 * We model that guard logic here without mounting the full React tree.
 */

type AgenticUiLike = {
  actions?: { id: string; label: string }[];
};

type MessageLike = {
  streaming?: boolean;
  options?: { action: string; label: string }[];
  agentic_ui?: AgenticUiLike | null;
  actions?: { id: string; label: string }[];
};

/** Mirrors the guard added in page.tsx line ~1892 */
function shouldRenderOptionButtons(m: MessageLike): boolean {
  return (
    !m.streaming &&
    !!m.options &&
    m.options.length > 0 &&
    !m.agentic_ui?.actions?.length   // BUG-11 guard: skip when agentic_ui.actions absorbed them
  );
}

/** Mirrors the existing guard at page.tsx line ~1895 */
function shouldRenderAgenticActions(m: MessageLike): boolean {
  return (
    !m.streaming &&
    !!m.agentic_ui?.actions &&
    m.agentic_ui.actions.length > 0
  );
}

/** Returns how many button rows would render for a message */
function countButtonRows(m: MessageLike): number {
  let rows = 0;
  if (shouldRenderOptionButtons(m)) rows++;
  if (shouldRenderAgenticActions(m)) rows++;
  return rows;
}

const SAMPLE_OPTIONS = [
  { action: "a", label: "A) Option A" },
  { action: "b", label: "B) Option B" },
];

const SAMPLE_ACTIONS = [
  { id: "opt-aaa", label: "A) Option A" },
  { id: "opt-bbb", label: "B) Option B" },
];

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("BUG-11 option-button deduplication guard", () => {
  test("no buttons when message is streaming", () => {
    const m: MessageLike = {
      streaming: true,
      options: SAMPLE_OPTIONS,
      agentic_ui: { actions: SAMPLE_ACTIONS },
    };
    expect(countButtonRows(m)).toBe(0);
  });

  test("options only — no agentic_ui.actions — renders OptionButtons", () => {
    const m: MessageLike = { options: SAMPLE_OPTIONS };
    expect(shouldRenderOptionButtons(m)).toBe(true);
    expect(shouldRenderAgenticActions(m)).toBe(false);
    expect(countButtonRows(m)).toBe(1);
  });

  test("agentic_ui.actions only — renders ChatActionsRow", () => {
    const m: MessageLike = { agentic_ui: { actions: SAMPLE_ACTIONS } };
    expect(shouldRenderOptionButtons(m)).toBe(false);
    expect(shouldRenderAgenticActions(m)).toBe(true);
    expect(countButtonRows(m)).toBe(1);
  });

  test("BOTH options and agentic_ui.actions (1-A injection) — only ChatActionsRow renders, no duplicate", () => {
    const m: MessageLike = {
      options: SAMPLE_OPTIONS,
      agentic_ui: { actions: SAMPLE_ACTIONS },
    };
    // OptionButtons must be suppressed
    expect(shouldRenderOptionButtons(m)).toBe(false);
    // ChatActionsRow must still render
    expect(shouldRenderAgenticActions(m)).toBe(true);
    // Exactly one row — no duplicate
    expect(countButtonRows(m)).toBe(1);
  });

  test("agentic_ui present but no actions — OptionButtons still renders", () => {
    const m: MessageLike = {
      options: SAMPLE_OPTIONS,
      agentic_ui: { actions: [] },
    };
    expect(shouldRenderOptionButtons(m)).toBe(true);
    expect(countButtonRows(m)).toBe(1);
  });

  test("agentic_ui is null — OptionButtons renders", () => {
    const m: MessageLike = { options: SAMPLE_OPTIONS, agentic_ui: null };
    expect(shouldRenderOptionButtons(m)).toBe(true);
    expect(countButtonRows(m)).toBe(1);
  });

  test("no options and no agentic_ui.actions — zero button rows", () => {
    const m: MessageLike = {};
    expect(countButtonRows(m)).toBe(0);
  });
});
