"use client";

/**
 * GmailConnectionCard — settings card for the Gmail read-only connector (M0).
 *
 * Follows the Telegram opt-in block pattern in SettingsAtelier (notifications
 * panel): palette-driven styling, busy-ref guards, parent-provided toasts.
 *
 * States (connection state is shown INDEPENDENTLY of the sync flag — the flag
 * gates sync, never visibility/revocation):
 *   • not connected + sync off (RICO_ENABLE_GMAIL_SYNC) → "coming soon"
 *   • not connected + sync on → "Connect Gmail" (Google consent URL)
 *   • connected as <email> + sync on → "Sync now" + "Disconnect", last-synced
 *   • connected as <email> + sync off → "connected, sync currently disabled"
 *     with "Disconnect" still available (Sync/Connect disabled)
 *   • needs re-auth → warning + "Reconnect"
 *
 * Permission copy is deliberately plain: read-only — Rico cannot send, delete,
 * or modify email. Backend: /api/v1/integrations/gmail (JWT identity only).
 */

import { useEffect, useRef, useState } from "react";

import type { WorkspacePalette } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import {
    disconnectGmail,
    getGmailConnectUrl,
    getGmailStatus,
    syncGmail,
    type GmailStatusResponse,
} from "@/lib/api";
import { useTranslation } from "@/lib/translations";

export function GmailConnectionCard({
    palette,
    notify,
}: {
    palette: WorkspacePalette;
    notify?: (message: string, type: "success" | "error") => void;
}) {
    const { language } = useLanguage();
    const t = useTranslation(language);

    const [status, setStatus] = useState<GmailStatusResponse | null>(null);
    const [loaded, setLoaded] = useState(false);
    const busyRef = useRef(false);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        const ctrl = new AbortController();
        getGmailStatus(ctrl.signal)
            .then((s) => {
                setStatus(s);
                setLoaded(true);
            })
            .catch(() => {
                if (!ctrl.signal.aborted) setLoaded(true);
            });
        return () => ctrl.abort();
    }, []);

    // Google callback redirects back to /settings?gmail=connected|error|denied.
    useEffect(() => {
        if (typeof window === "undefined") return;
        const params = new URLSearchParams(window.location.search);
        const result = params.get("gmail");
        if (!result) return;
        if (result === "connected") {
            notify?.(t("gmailConnected"), "success");
        } else {
            notify?.(t("gmailActionFailed"), "error");
        }
        params.delete("gmail");
        const rest = params.toString();
        window.history.replaceState(
            null,
            "",
            `${window.location.pathname}${rest ? `?${rest}` : ""}`,
        );
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const withBusy = async (action: () => Promise<void>) => {
        if (busyRef.current) return;
        busyRef.current = true;
        setBusy(true);
        try {
            await action();
        } catch {
            notify?.(t("gmailActionFailed"), "error");
        } finally {
            busyRef.current = false;
            setBusy(false);
        }
    };

    const handleConnect = () =>
        withBusy(async () => {
            const { auth_url } = await getGmailConnectUrl();
            window.location.assign(auth_url);
        });

    const handleSync = () =>
        withBusy(async () => {
            await syncGmail();
            notify?.(t("gmailSyncStarted"), "success");
        });

    const handleDisconnect = () =>
        withBusy(async () => {
            await disconnectGmail();
            const next = await getGmailStatus();
            setStatus(next);
            notify?.(t("gmailDisconnected"), "success");
        });

    // The flag gates SYNC, not visibility. A connected user must always see the
    // live connection (and be able to disconnect it) even while sync is off.
    const syncEnabled = Boolean(status?.sync_enabled ?? status?.enabled);
    const connected = Boolean(status?.connected);
    const needsReauth = Boolean(status?.needs_reauth);

    const stateLine = (() => {
        if (!loaded) return "…";
        if (needsReauth) return t("gmailNeedsReauth");
        if (connected) {
            const base = status?.provider_email
                ? t("gmailConnectedAs").replace("{email}", status.provider_email)
                : t("gmailConnected");
            // Connected but sync paused: show the connection, note sync is off.
            return syncEnabled ? base : `${base} — ${t("gmailSyncDisabled")}`;
        }
        // Not connected: distinguish "feature not enabled yet" from "connect me".
        if (!syncEnabled) return t("gmailComingSoon");
        return t("gmailNotConnected");
    })();

    const lastSynced =
        connected && status?.last_sync_at
            ? t("gmailLastSynced").replace(
                  "{time}",
                  new Date(status.last_sync_at).toLocaleString(
                      language === "ar" ? "ar-AE" : "en-AE",
                  ),
              )
            : null;

    const solidBtn: React.CSSProperties = {
        background: palette.ink,
        color: palette.bg,
        opacity: busy || !syncEnabled ? 0.55 : 1,
        cursor: busy || !syncEnabled ? "default" : "pointer",
    };
    const outlineBtn: React.CSSProperties = {
        background: "transparent",
        color: palette.red,
        border: `1px solid ${palette.red}`,
        opacity: busy ? 0.55 : 1,
        cursor: busy ? "default" : "pointer",
    };
    const btnClass =
        "inline-flex items-center gap-2 rounded-[6px] px-4 py-2.5 text-[13px] font-semibold transition-opacity";

    return (
        <div
            className="flex flex-col gap-3 pt-5"
            style={{ borderTop: `1px solid ${palette.hair}` }}
        >
            <div className="min-w-0">
                <p className="text-[14px] font-semibold" style={{ color: palette.ink }}>
                    {t("gmailSectionTitle")}
                </p>
                <p
                    className="mt-1 flex items-center gap-1.5 text-[12px]"
                    style={{ color: palette.ink55 }}
                >
                    <span
                        className="h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{
                            background:
                                connected && !needsReauth ? palette.red : palette.ink40,
                        }}
                    />
                    {stateLine}
                </p>
                {lastSynced && (
                    <p className="mt-1 text-[12px]" style={{ color: palette.ink40 }}>
                        {lastSynced}
                    </p>
                )}
                <p className="mt-2 text-[12px]" style={{ color: palette.ink55 }}>
                    {t("gmailReadOnlyNote")}
                </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
                {!connected && !needsReauth && (
                    <button
                        type="button"
                        onClick={handleConnect}
                        disabled={busy || !syncEnabled}
                        className={btnClass}
                        style={solidBtn}
                    >
                        {t("gmailConnect")}
                    </button>
                )}
                {needsReauth && (
                    <button
                        type="button"
                        onClick={handleConnect}
                        disabled={busy || !syncEnabled}
                        className={btnClass}
                        style={solidBtn}
                    >
                        {t("gmailReconnect")}
                    </button>
                )}
                {connected && !needsReauth && (
                    <button
                        type="button"
                        onClick={handleSync}
                        disabled={busy || !syncEnabled}
                        className={btnClass}
                        style={solidBtn}
                    >
                        {t("gmailSyncNow")}
                    </button>
                )}
                {(connected || needsReauth) && (
                    <button
                        type="button"
                        onClick={handleDisconnect}
                        disabled={busy}
                        className={btnClass}
                        style={outlineBtn}
                    >
                        {t("gmailDisconnect")}
                    </button>
                )}
            </div>
        </div>
    );
}
