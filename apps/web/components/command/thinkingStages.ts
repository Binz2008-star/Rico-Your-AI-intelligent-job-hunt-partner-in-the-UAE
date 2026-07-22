"use client";

/**
 * Shared thinking-stage clock for the Command chat's waiting states
 * (RicoThinking in the authenticated transcript, WorkingIndicator on the
 * public surface). While Rico has accepted a turn but produced no text, the
 * label evolves through honest, generic stages instead of sitting frozen —
 * the wording never claims specific work (no "scanning feeds" while idle),
 * it only acknowledges that time is passing and the request is still held.
 *
 * Stage boundaries: 0s "Thinking…" → 6s "Working through it…" → 16s the
 * long-haul line. `elapsed` ticks every second so callers can surface the
 * modern-AI elapsed stamp ("12s") once the wait is long enough to explain.
 */

import { useEffect, useState } from "react";

const STAGES = {
    en: [
        "Thinking…",
        "Working through it…",
        "Still on it — this one deserves care…",
    ],
    ar: [
        "أُفكّر…",
        "أشتغل عليها…",
        "ما زلت أعمل — طلبك يستحقّ التأنّي…",
    ],
} as const;

const STAGE_2_AT_S = 6;
const STAGE_3_AT_S = 16;

export function useThinkingStages(isAr: boolean): {
    label: string;
    stage: number;
    elapsed: number;
} {
    const [elapsed, setElapsed] = useState(0);
    useEffect(() => {
        const id = setInterval(() => setElapsed((s) => s + 1), 1000);
        return () => clearInterval(id);
    }, []);
    const stage = elapsed >= STAGE_3_AT_S ? 2 : elapsed >= STAGE_2_AT_S ? 1 : 0;
    return { label: STAGES[isAr ? "ar" : "en"][stage], stage, elapsed };
}
