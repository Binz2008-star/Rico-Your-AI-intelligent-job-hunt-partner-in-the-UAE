"use client";

/**
 * Reference-only action notice for the Atelier Console gallery entry.
 *
 * The ported console wires every interactive action button (apply, save, send,
 * track, follow-up, …) to `showPrototypeNotice("forbidden")`. In the gallery
 * these actions are intentionally NON-functional: clicking one surfaces this
 * small toast making the reference-only status explicit. No real chat, job,
 * apply, save, or CV action is performed anywhere.
 */

import { useEffect, useState } from "react";

type Kind = "forbidden";

const EVENT = "atelier-console:prototype-notice";

export function showPrototypeNotice(_kind: Kind = "forbidden") {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(EVENT));
}

export function PrototypeNoticeToast() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    function onNotice() {
      setVisible(true);
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => setVisible(false), 2600);
    }
    window.addEventListener(EVENT, onNotice);
    return () => {
      window.removeEventListener(EVENT, onNotice);
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed bottom-6 left-1/2 z-[60] -translate-x-1/2"
    >
      <span className="inline-flex items-center gap-2 rounded-full border border-[var(--sun)]/60 bg-[var(--card)] px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--ink)] shadow-[0_10px_30px_-12px_rgba(20,17,13,0.5)]">
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--sun)]" />
        Reference only — action disabled in gallery
      </span>
    </div>
  );
}
