"use client";

import { useEffect, useState } from "react";

export function PWAUpdatePrompt() {
  const [showUpdate, setShowUpdate] = useState(false);
  const [waitingWorker, setWaitingWorker] = useState<ServiceWorker | null>(
    null,
  );

  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator))
      return;

    let refreshing = false;

    const onControllerChange = () => {
      if (refreshing) return;
      refreshing = true;
      window.location.reload();
    };

    navigator.serviceWorker.addEventListener(
      "controllerchange",
      onControllerChange,
    );

    navigator.serviceWorker.ready.then((registration) => {
      if (registration.waiting) {
        setWaitingWorker(registration.waiting);
        setShowUpdate(true);
      }

      const onUpdateFound = () => {
        const newWorker = registration.installing;
        if (!newWorker) return;

        newWorker.addEventListener("statechange", () => {
          if (
            newWorker.state === "installed" &&
            navigator.serviceWorker.controller &&
            registration.waiting
          ) {
            setWaitingWorker(registration.waiting);
            setShowUpdate(true);
          }
        });
      };

      registration.addEventListener("updatefound", onUpdateFound);

      return () => {
        registration.removeEventListener("updatefound", onUpdateFound);
      };
    });

    return () => {
      navigator.serviceWorker.removeEventListener(
        "controllerchange",
        onControllerChange,
      );
    };
  }, []);

  const handleUpdate = () => {
    waitingWorker?.postMessage({ type: "SKIP_WAITING" });
  };

  if (!showUpdate) return null;

  return (
    <div className="fixed bottom-[calc(1rem+env(safe-area-inset-bottom))] left-4 right-4 z-[9999] sm:left-auto sm:w-96">
      <div className="rounded-xl border border-border-subtle bg-surface p-4 shadow-lg">
        <p className="mb-3 text-sm font-medium text-text-primary">
          New version available
        </p>
        <div className="flex gap-2">
          <button
            onClick={handleUpdate}
            className="flex-1 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary"
          >
            Refresh
          </button>
          <button
            onClick={() => setShowUpdate(false)}
            className="rounded-lg border border-border-subtle px-4 py-2 text-sm text-text-secondary"
          >
            Later
          </button>
        </div>
      </div>
    </div>
  );
}
