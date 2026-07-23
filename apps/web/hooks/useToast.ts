"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type ToastVariant = "success" | "error" | "info";

export interface Toast {
  id: string;
  message: string;
  variant: ToastVariant;
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Track the component's mounted state and every pending auto-dismiss timer so
  // that (a) a timer never calls setState after unmount — which in a torn-down
  // jsdom/test environment throws "window is not defined", and in the browser
  // is a benign-but-real setState-on-unmounted-component leak — and (b) all
  // outstanding timers are cleared when the hook unmounts.
  const mountedRef = useRef(true);
  const timersRef = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());
  // Mirror of toasts for synchronous dedup checks without reading state in
  // the callback (avoids stale-closure issues).
  const toastsRef = useRef<Toast[]>([]);

  useEffect(() => {
    mountedRef.current = true;
    const timers = timersRef.current;
    return () => {
      mountedRef.current = false;
      for (const timer of timers) {
        clearTimeout(timer);
      }
      timers.clear();
    };
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => {
      const next = prev.filter((t) => t.id !== id);
      toastsRef.current = next;
      return next;
    });
  }, []);

  const toast = useCallback(
    (message: string, variant: ToastVariant = "info", duration = 3500) => {
      // Dedupe: if an identical toast (same message + variant) is already
      // visible, refresh its timer instead of stacking a duplicate (#1217).
      const existing = toastsRef.current.find(
        (t) => t.message === message && t.variant === variant,
      );
      if (existing) {
        // Clear all timers and set a fresh one for the existing toast.
        for (const timer of timersRef.current) {
          clearTimeout(timer);
          timersRef.current.delete(timer);
        }
        const id = existing.id;
        const timer = setTimeout(() => {
          timersRef.current.delete(timer);
          if (!mountedRef.current) return;
          dismiss(id);
        }, duration);
        timersRef.current.add(timer);
        return;
      }
      const id = crypto.randomUUID();
      const next = [...toastsRef.current, { id, message, variant }];
      toastsRef.current = next;
      setToasts(next);
      const timer = setTimeout(() => {
        timersRef.current.delete(timer);
        if (!mountedRef.current) return;
        dismiss(id);
      }, duration);
      timersRef.current.add(timer);
    },
    [dismiss],
  );

  return { toasts, toast, dismiss };
}
