"use client";

/**
 * ProfileAvatar — the profile hero avatar with change/remove controls
 * (owner request 2026-07-21; backend: /api/v1/user/avatar, migration 050).
 *
 * Behavior contract:
 *  - Shows the stored avatar image, or the initials fallback (previous look)
 *    while none exists / while loading / on fetch failure (fail-open).
 *  - "Change photo" downscales client-side (canvas → 512px JPEG) so the
 *    upload stays tiny; if canvas is unavailable the original file is sent
 *    as-is (the backend still enforces type + 500 KB).
 *  - Backend-authoritative: the preview only switches after the server
 *    confirms; errors surface inline and never fake success.
 */

import { deleteAvatar, getAvatar, uploadAvatar } from "@/lib/api";
import { useLanguage } from "@/contexts/LanguageContext";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useCallback, useEffect, useRef, useState } from "react";

const T = {
    en: {
        change: "Change photo",
        remove: "Remove",
        uploading: "Uploading…",
        alt: "Profile photo",
        error: "Couldn't update the photo. Try a JPEG/PNG under 500 KB.",
    },
    ar: {
        change: "تغيير الصورة",
        remove: "إزالة",
        uploading: "جارٍ الرفع…",
        alt: "الصورة الشخصية",
        error: "تعذّر تحديث الصورة. جرّب JPEG/PNG بحجم أقل من 500 كيلوبايت.",
    },
} as const;

const MAX_EDGE = 512;

/** Downscale to a ≤512px JPEG blob; falls back to the original file when the
 *  canvas pipeline is unavailable (old browsers, test environments). */
async function downscale(file: File): Promise<Blob> {
    try {
        const bitmap = await createImageBitmap(file);
        const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
        const w = Math.max(1, Math.round(bitmap.width * scale));
        const h = Math.max(1, Math.round(bitmap.height * scale));
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (!ctx) return file;
        ctx.drawImage(bitmap, 0, 0, w, h);
        const blob = await new Promise<Blob | null>((resolve) =>
            canvas.toBlob(resolve, "image/jpeg", 0.85),
        );
        return blob ?? file;
    } catch {
        return file;
    }
}

export function ProfileAvatar({
    initials,
    size = 104,
}: {
    /** Initials fallback (the previous static circle's content). */
    initials: string;
    size?: number;
}) {
    const { language } = useLanguage();
    const t = T[language];
    const c = useWorkspaceTheme();
    const [avatar, setAvatar] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        let cancelled = false;
        getAvatar()
            .then((r) => { if (!cancelled) setAvatar(r.avatar); })
            .catch(() => { /* fail-open: initials fallback */ });
        return () => { cancelled = true; };
    }, []);

    const onFile = useCallback(async (file: File) => {
        setBusy(true);
        setError(false);
        try {
            const blob = await downscale(file);
            const res = await uploadAvatar(blob);
            setAvatar(res.avatar);
        } catch {
            setError(true);
        } finally {
            setBusy(false);
        }
    }, []);

    const onRemove = useCallback(async () => {
        setBusy(true);
        setError(false);
        try {
            await deleteAvatar();
            setAvatar(null);
        } catch {
            setError(true);
        } finally {
            setBusy(false);
        }
    }, []);

    return (
        <div className="flex flex-col items-center gap-2">
            <div
                className="relative flex items-center justify-center overflow-hidden rounded-full"
                style={{
                    width: size,
                    height: size,
                    background: `color-mix(in srgb, ${c.red} 12%, transparent)`,
                    color: c.red,
                    border: `1px solid ${c.hair}`,
                }}
            >
                {avatar ? (
                    // Data-URL image — next/image adds nothing for inline data URIs.
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                        src={avatar}
                        alt={t.alt}
                        data-testid="profile-avatar-image"
                        className="h-full w-full object-cover"
                    />
                ) : (
                    <span aria-hidden className="text-[34px] font-medium" style={{ fontFamily: "var(--font-fraunces-landing), Georgia, serif" }}>
                        {initials}
                    </span>
                )}
            </div>
            <div className="flex items-center gap-2">
                <button
                    type="button"
                    data-testid="profile-avatar-change"
                    onClick={() => inputRef.current?.click()}
                    disabled={busy}
                    className="rounded-full px-3 py-1 text-[11px] font-semibold disabled:opacity-50"
                    style={{ border: `1px solid ${c.hair}`, color: c.ink70, background: "transparent", cursor: "pointer" }}
                >
                    {busy ? t.uploading : t.change}
                </button>
                {avatar && !busy && (
                    <button
                        type="button"
                        data-testid="profile-avatar-remove"
                        onClick={() => void onRemove()}
                        className="rounded-full px-3 py-1 text-[11px] font-semibold"
                        style={{ border: `1px solid ${c.hair}`, color: c.ink55, background: "transparent", cursor: "pointer" }}
                    >
                        {t.remove}
                    </button>
                )}
            </div>
            {error && (
                <p role="alert" className="max-w-[180px] text-center text-[10.5px] leading-snug" style={{ color: c.red }}>
                    {t.error}
                </p>
            )}
            <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                aria-label={t.change}
                onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void onFile(f);
                    e.target.value = "";
                }}
            />
        </div>
    );
}
