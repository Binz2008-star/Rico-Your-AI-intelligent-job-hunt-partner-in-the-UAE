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

  const toast = useCallback(
    (message: string, variant: ToastVariant = "info", duration = 3500) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { id, message, variant }]);
      const timer = setTimeout(() => {
        timersRef.current.delete(timer);
        if (!mountedRef.current) return;
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, duration);
      timersRef.current.add(timer);
    },
    []
  );

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, toast, dismiss };
}
