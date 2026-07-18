"use client";

/**
 * GmailConnectionCard — settings card for the Gmail read-only connector (M0).
 *
 * Follows the Telegram opt-in block pattern in SettingsAtelier (notifications
 * panel): palette-driven styling, busy-ref guards, parent-provided toasts.
 *
 * Connection state is shown INDEPENDENTLY of the sync flag — the flag gates
 * sync, never visibility/revocation:
 *   • not connected + sync off (RICO_ENABLE_GMAIL_SYNC) → "coming soon"
 *   • not connected + sync on → "Connect Gmail" (Google consent URL)
 *   • connected + sync on → "Sync now" + recurring-sync consent + "Disconnect"
 *   • connected + sync off → "connected, sync currently disabled" (Disconnect
 *     and consent revoke stay available; Sync/Connect disabled)
 *   • needs re-auth → warning + "Reconnect"
 *
 * Recurring-sync consent (separate opt-in from the OAuth read grant): the user
 * must explicitly approve background/fleet sync AFTER an informed disclosure —
 * never a preselected checkbox, never bundled with unrelated consent. This maps
 * to the backend's dedicated `POST /consent` contract and the truthful
 * `recurring_sync_consent` field on `/status`. Nothing here enables Gmail in
 * production; when the feature flag is off the connect path stays disabled and
 * a connection cannot be reached, so the consent/disconnect affordances are only
 * shown when the backend actually reports a live connection.
 *
 * Permission copy is deliberately plain: read-only — Rico cannot send, delete,
 * or modify email. Backend: /api/v1/integrations/gmail (JWT identity only). The
 * encrypted refresh token is never part of any payload this card receives.
 */

import { useEffect, useRef, useState } from "react";

import type { WorkspacePalette } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import {
    disconnectGmail,
    getGmailConnectUrl,
    getGmailStatus,
    setGmailRecurringSyncConsent,
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
    // Recurring-sync consent: the disclosure panel is collapsed by default and
    // the approval checkbox always starts UNCHECKED (never preselected).
    const [consentOpen, setConsentOpen] = useState(false);
    const [consentChecked, setConsentChecked] = useState(false);
    // Two-step disconnect confirmation (a revoke is consequential).
    const [confirmingDisconnect, setConfirmingDisconnect] = useState(false);

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

    const refreshStatus = async () => {
        const next = await getGmailStatus();
        setStatus(next);
        return next;
    };

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

    // Grant recurring-sync consent — only reachable after the user has ticked
    // the explicit approval checkbox in the open disclosure panel.
    const handleGrantConsent = () =>
        withBusy(async () => {
            await setGmailRecurringSyncConsent(true);
            await refreshStatus();
            setConsentOpen(false);
            setConsentChecked(false);
            notify?.(t("gmailConsentGranted"), "success");
        });

    // Revoke is a privacy-reducing action — always available while connected,
    // even when sync is disabled, and never requires the checkbox.
    const handleRevokeConsent = () =>
        withBusy(async () => {
            await setGmailRecurringSyncConsent(false);
            await refreshStatus();
            notify?.(t("gmailConsentRevoked"), "success");
        });

    const handleDisconnect = () =>
        withBusy(async () => {
            await disconnectGmail();
            await refreshStatus();
            setConfirmingDisconnect(false);
            setConsentOpen(false);
            setConsentChecked(false);
            notify?.(t("gmailDisconnected"), "success");
        });

    // The flag gates SYNC, not visibility. A connected user must always see the
    // live connection (and be able to disconnect it) even while sync is off.
    const syncEnabled = Boolean(status?.sync_enabled ?? status?.enabled);
    const connected = Boolean(status?.connected);
    const needsReauth = Boolean(status?.needs_reauth);
    const recurringConsent = Boolean(status?.recurring_sync_consent);

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
    const neutralBtn: React.CSSProperties = {
        background: "transparent",
        color: palette.ink,
        border: `1px solid ${palette.hair}`,
        opacity: busy ? 0.55 : 1,
        cursor: busy ? "default" : "pointer",
    };
    const btnClass =
        "inline-flex items-center gap-2 rounded-[6px] px-4 py-2.5 text-[13px] font-semibold transition-opacity motion-reduce:transition-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2";

    // Consent disclosure bullets — every required disclosure, plain language.
    const consentBullets = [
        "gmailConsentReadOnly",
        "gmailConsentJobOnly",
        "gmailConsentMetadata",
        "gmailConsentStored",
        "gmailConsentWhyStored",
        "gmailConsentNoSend",
        "gmailConsentNoSilent",
        "gmailConsentReviewUpdates",
        "gmailConsentDisconnectNote",
        "gmailConsentDeleteNote",
    ] as const;

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

            {/* Primary connection actions */}
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
                {(connected || needsReauth) && !confirmingDisconnect && (
                    <button
                        type="button"
                        onClick={() => setConfirmingDisconnect(true)}
                        disabled={busy}
                        className={btnClass}
                        style={outlineBtn}
                    >
                        {t("gmailDisconnect")}
                    </button>
                )}
            </div>

            {/* Recurring-sync consent — only while a live connection is reported */}
            {connected && !needsReauth && (
                <div
                    className="mt-1 flex flex-col gap-2 rounded-[8px] p-3"
                    style={{ border: `1px solid ${palette.hair}` }}
                    data-testid="gmail-consent-section"
                >
                    <p
                        className="flex items-center gap-1.5 text-[12px] font-semibold"
                        style={{ color: palette.ink }}
                    >
                        <span
                            className="h-1.5 w-1.5 shrink-0 rounded-full"
                            style={{
                                background: recurringConsent
                                    ? palette.red
                                    : palette.ink40,
                            }}
                        />
                        {recurringConsent
                            ? t("gmailConsentApproved")
                            : t("gmailConsentNotApproved")}
                    </p>

                    {recurringConsent ? (
                        <button
                            type="button"
                            onClick={handleRevokeConsent}
                            disabled={busy}
                            className={btnClass}
                            style={outlineBtn}
                        >
                            {t("gmailConsentRevoke")}
                        </button>
                    ) : consentOpen ? (
                        <div
                            role="region"
                            aria-label={t("gmailConsentTitle")}
                            className="flex flex-col gap-2"
                        >
                            <p className="text-[12px]" style={{ color: palette.ink55 }}>
                                {t("gmailConsentIntro")}
                            </p>
                            <ul
                                className="flex flex-col gap-1 text-[12px]"
                                style={{ color: palette.ink55 }}
                            >
                                {consentBullets.map((key) => (
                                    <li key={key} className="flex gap-1.5">
                                        <span aria-hidden="true">•</span>
                                        <span>{t(key)}</span>
                                    </li>
                                ))}
                            </ul>
                            <label
                                className="mt-1 flex cursor-pointer items-start gap-2 text-[12px]"
                                style={{ color: palette.ink }}
                            >
                                <input
                                    type="checkbox"
                                    checked={consentChecked}
                                    onChange={(e) =>
                                        setConsentChecked(e.target.checked)
                                    }
                                    className="mt-0.5 h-4 w-4 shrink-0"
                                    aria-describedby="gmail-consent-terms"
                                />
                                <span id="gmail-consent-terms">
                                    {t("gmailConsentCheckbox")}
                                </span>
                            </label>
                            <div className="flex flex-wrap items-center gap-3">
                                <button
                                    type="button"
                                    onClick={handleGrantConsent}
                                    disabled={busy || !consentChecked}
                                    className={btnClass}
                                    style={{
                                        ...solidBtn,
                                        opacity:
                                            busy || !consentChecked ? 0.55 : 1,
                                        cursor:
                                            busy || !consentChecked
                                                ? "default"
                                                : "pointer",
                                    }}
                                >
                                    {t("gmailConsentGrant")}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setConsentOpen(false);
                                        setConsentChecked(false);
                                    }}
                                    disabled={busy}
                                    className={btnClass}
                                    style={neutralBtn}
                                >
                                    {t("gmailConsentCancel")}
                                </button>
                            </div>
                        </div>
                    ) : (
                        <button
                            type="button"
                            onClick={() => setConsentOpen(true)}
                            disabled={busy}
                            className={btnClass}
                            style={neutralBtn}
                        >
                            {t("gmailConsentReview")}
                        </button>
                    )}
                </div>
            )}

            {/* Disconnect confirmation — a revoke is consequential */}
            {(connected || needsReauth) && confirmingDisconnect && (
                <div
                    role="region"
                    aria-label={t("gmailDisconnectConfirmTitle")}
                    className="mt-1 flex flex-col gap-2 rounded-[8px] p-3"
                    style={{ border: `1px solid ${palette.red}` }}
                    data-testid="gmail-disconnect-confirm"
                >
                    <p className="text-[12px] font-semibold" style={{ color: palette.ink }}>
                        {t("gmailDisconnectConfirmTitle")}
                    </p>
                    <p className="text-[12px]" style={{ color: palette.ink55 }}>
                        {t("gmailDisconnectConfirmBody")}
                    </p>
                    <div className="flex flex-wrap items-center gap-3">
                        <button
                            type="button"
                            onClick={handleDisconnect}
                            disabled={busy}
                            className={btnClass}
                            style={outlineBtn}
                        >
                            {t("gmailDisconnectConfirm")}
                        </button>
                        <button
                            type="button"
                            onClick={() => setConfirmingDisconnect(false)}
                            disabled={busy}
                            className={btnClass}
                            style={neutralBtn}
                        >
                            {t("gmailConsentCancel")}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
