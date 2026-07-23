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

  // Track the component's mounted state and each toast's auto-dismiss timer so
  // timers never update state after unmount and one toast can be refreshed or
  // dismissed without cancelling unrelated toast timers.
  const mountedRef = useRef(true);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(
    new Map(),
  );
  // Mirror of toasts for synchronous dedup checks without reading state in
  // the callback (avoids stale-closure issues).
  const toastsRef = useRef<Toast[]>([]);

  useEffect(() => {
    mountedRef.current = true;
    const timers = timersRef.current;
    return () => {
      mountedRef.current = false;
      for (const timer of timers.values()) {
        clearTimeout(timer);
      }
      timers.clear();
    };
  }, []);

  const dismiss = useCallback((id: string) => {
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }

    setToasts((prev) => {
      const next = prev.filter((toast) => toast.id !== id);
      toastsRef.current = next;
      return next;
    });
  }, []);

  const scheduleDismiss = useCallback(
    (id: string, duration: number) => {
      const existingTimer = timersRef.current.get(id);
      if (existingTimer) {
        clearTimeout(existingTimer);
      }

      const timer = setTimeout(() => {
        timersRef.current.delete(id);
        if (!mountedRef.current) return;
        dismiss(id);
      }, duration);
      timersRef.current.set(id, timer);
    },
    [dismiss],
  );

  const toast = useCallback(
    (message: string, variant: ToastVariant = "info", duration = 3500) => {
      // Dedupe: if an identical toast (same message + variant) is already
      // visible, refresh only that toast's timer instead of stacking it or
      // disturbing unrelated notifications (#1217).
      const existing = toastsRef.current.find(
        (item) => item.message === message && item.variant === variant,
      );
      if (existing) {
        scheduleDismiss(existing.id, duration);
        return;
      }

      const id = crypto.randomUUID();
      const next = [...toastsRef.current, { id, message, variant }];
      toastsRef.current = next;
      setToasts(next);
      scheduleDismiss(id, duration);
    },
    [scheduleDismiss],
  );

  return { toasts, toast, dismiss };
}
