import {
  verifyLink,
  verifyLinkBatch,
  type LinkVerificationResult,
} from "@/lib/api";
import type { OpportunitySignal } from "@/lib/api/orchestration";
import { useCallback, useEffect, useRef, useState } from "react";

type UILinkStatus = LinkVerificationResult["status"] | "checking";

interface UILinkVerificationResult {
  status: UILinkStatus;
  http_status: number | null;
  error_message: string | null;
  verified_at: string;
  redirect_url?: string;
}

const VERIFICATION_CACHE = new Map<string, LinkVerificationResult>();
const MAX_VISIBLE_TO_VERIFY = 12;

export function useLinkVerification(signals: OpportunitySignal[]) {
  const [verificationResults, setVerificationResults] = useState<
    Record<string, UILinkVerificationResult>
  >({});
  const [isVerifying, setIsVerifying] = useState(false);
  // Ref-based guard prevents the callback from changing identity on every
  // isVerifying state flip, which would otherwise create an infinite loop:
  // setIsVerifying → new verifyVisibleSignals → useEffect re-fires → repeat.
  const isRunningRef = useRef(false);

  const getUrlToVerify = useCallback(
    (signal: OpportunitySignal): string | null => {
      return signal.applyUrl || signal.sourceUrl || null;
    },
    [],
  );

  const verifyUrl = useCallback(
    async (url: string): Promise<LinkVerificationResult | null> => {
      // Check cache first
      if (VERIFICATION_CACHE.has(url)) {
        return VERIFICATION_CACHE.get(url)!;
      }

      try {
        const result = await verifyLink(url);
        VERIFICATION_CACHE.set(url, result);
        return result;
      } catch (error) {
        console.error("Link verification failed:", error);
        return null;
      }
    },
    [],
  );

  const verifyBatch = useCallback(
    async (
      urls: string[],
    ): Promise<Record<string, LinkVerificationResult | null>> => {
      const uncachedUrls = urls.filter((url) => !VERIFICATION_CACHE.has(url));

      if (uncachedUrls.length === 0) {
        return urls.reduce(
          (acc, url) => {
            acc[url] = VERIFICATION_CACHE.get(url)!;
            return acc;
          },
          {} as Record<string, LinkVerificationResult>,
        );
      }

      // Use batch API if available, otherwise fall back to individual calls
      try {
        const batchResults =
          await verifyLinkBatch(uncachedUrls);

        // Cache results
        Object.entries(batchResults).forEach(([url, result]) => {
          VERIFICATION_CACHE.set(url, result);
        });

        return urls.reduce(
          (acc, url) => {
            acc[url] = VERIFICATION_CACHE.get(url)!;
            return acc;
          },
          {} as Record<string, LinkVerificationResult>,
        );
      } catch (error) {
        console.error(
          "Batch verification failed, falling back to individual calls:",
          error,
        );

        // Fall back to individual calls
        const results: Record<string, LinkVerificationResult | null> = {};
        for (const url of urls) {
          results[url] = await verifyUrl(url);
        }
        return results;
      }
    },
    [verifyUrl],
  );

  const verifyVisibleSignals = useCallback(async () => {
    if (isRunningRef.current) return;

    isRunningRef.current = true;
    setIsVerifying(true);

    // Get first MAX_VISIBLE_TO_VERIFY signals with URLs
    const signalsToVerify = signals
      .slice(0, MAX_VISIBLE_TO_VERIFY)
      .filter((signal) => getUrlToVerify(signal) !== null);

    if (signalsToVerify.length === 0) {
      setIsVerifying(false);
      return;
    }

    // Set checking status
    const checkingIds = signalsToVerify.map((s) => s.id);
    setVerificationResults((prev) => {
      const updated = { ...prev };
      checkingIds.forEach((id) => {
        updated[id] = {
          status: "checking",
          http_status: null,
          error_message: null,
          verified_at: new Date().toISOString(),
        };
      });
      return updated;
    });

    // Collect URLs
    const urlToSignalMap = new Map<string, string>();
    signalsToVerify.forEach((signal) => {
      const url = getUrlToVerify(signal);
      if (url) {
        urlToSignalMap.set(url, signal.id);
      }
    });

    const urls = Array.from(urlToSignalMap.keys());

    // Verify in batches
    const results = await verifyBatch(urls);

    // Map results back to signal IDs
    setVerificationResults((prev) => {
      const updated = { ...prev };
      urlToSignalMap.forEach((signalId, url) => {
        const result = results[url];
        if (result) {
          updated[signalId] = result;
        } else {
          // Error fallback
          updated[signalId] = {
            status: "needs_review",
            http_status: null,
            error_message: "Verification failed",
            verified_at: new Date().toISOString(),
          };
        }
      });
      return updated;
    });

    isRunningRef.current = false;
    setIsVerifying(false);
  }, [signals, getUrlToVerify, verifyBatch]);

  // Auto-verify when signals change
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      void verifyVisibleSignals();
    }, 500); // Small delay to not block initial render

    return () => clearTimeout(timeoutId);
  }, [signals, verifyVisibleSignals]);

  const getLinkStatus = useCallback(
    (signalId: string): UILinkStatus | undefined => {
      const result = verificationResults[signalId];
      return result?.status || undefined;
    },
    [verificationResults],
  );

  const isChecking = useCallback(
    (signalId: string): boolean => {
      return verificationResults[signalId]?.status === "checking";
    },
    [verificationResults],
  );

  return {
    verificationResults,
    isVerifying,
    getLinkStatus,
    isChecking,
    verifyVisibleSignals,
  };
}
