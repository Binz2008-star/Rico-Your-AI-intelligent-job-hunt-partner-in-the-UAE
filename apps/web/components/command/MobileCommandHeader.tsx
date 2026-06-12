"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { useTheme } from "@/contexts/ThemeContext";
import { fetchMe } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

type ChatAudience = "checking" | "authenticated" | "public";

interface MobileCommandHeaderProps {
    chatAudience: ChatAudience;
    onLogout: () => void;
    onNewChat: () => void;
    onClearChat: () => void;
    loginHref: string;
    signupHref: string;
}

// ── Inline SVG icon components ──────────────────────────────────────────────

function IconPerson() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20a8 8 0 0 1 16 0" />
        </svg>
    );
}

function IconDocument() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
        </svg>
    );
}

function IconClipboard() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="9" y="2" width="6" height="4" rx="1" />
            <path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2" />
            <path d="M9 12h6M9 16h4" />
        </svg>
    );
}

function IconStar() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
    );
}

function IconGlobe() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="2" y1="12" x2="22" y2="12" />
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
    );
}

function IconSun() {
    return (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
        </svg>
    );
}

function IconMoon() {
    return (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
    );
}

function IconTrash() {
    return (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
        </svg>
    );
}

function IconHistory() {
    return (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
            <path d="M3 3v5h5" />
            <path d="M12 7v5l4 2" />
        </svg>
    );
}

function IconSettings() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
    );
}

function IconLogout() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
        </svg>
    );
}

export function MobileCommandHeader({
    chatAudience,
    onLogout,
    onNewChat,
    onClearChat,
    loginHref,
    signupHref,
}: MobileCommandHeaderProps) {
    const { language, setLanguage } = useLanguage();
    const { resolvedTheme, setTheme } = useTheme();
    const t = useTranslation(language);
    const pathname = usePathname();
    const isDark = resolvedTheme === "dark";
    const isRTL = language === "ar";

    const [drawerOpen, setDrawerOpen] = useState(false);
    const [overflowOpen, setOverflowOpen] = useState(false);
    const [userEmail, setUserEmail] = useState<string | null>(null);
    const overflowRef = useRef<HTMLDivElement>(null);
    const drawerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (chatAudience !== "authenticated") return;
        fetchMe().then((me) => { if (me.authenticated && me.email) setUserEmail(me.email); }).catch(() => {});
    }, [chatAudience]);

    useEffect(() => {
        if (drawerOpen) {
            document.body.style.overflow = "hidden";
        } else {
            document.body.style.overflow = "";
        }
        return () => {
            document.body.style.overflow = "";
        };
    }, [drawerOpen]);

    useEffect(() => {
        if (!overflowOpen) return;
        function handle(e: MouseEvent) {
            if (overflowRef.current && !overflowRef.current.contains(e.target as Node)) {
                setOverflowOpen(false);
            }
        }
        document.addEventListener("mousedown", handle);
        return () => document.removeEventListener("mousedown", handle);
    }, [overflowOpen]);

    useEffect(() => {
        if (!drawerOpen) return;
        function handle(e: MouseEvent) {
            if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
                setDrawerOpen(false);
            }
        }
        function handleKey(e: KeyboardEvent) {
            if (e.key === "Escape") setDrawerOpen(false);
        }
        document.addEventListener("mousedown", handle);
        document.addEventListener("keydown", handleKey);
        return () => {
            document.removeEventListener("mousedown", handle);
            document.removeEventListener("keydown", handleKey);
        };
    }, [drawerOpen]);

    const drawerItems =
        chatAudience === "authenticated"
            ? [
                  { label: t("profileTitle"), href: "/profile", icon: <IconPerson /> },
                  { label: t("uploadCv"), href: "/upload", icon: <IconDocument /> },
                  { label: t("navPipeline"), href: "/flow", icon: <IconClipboard /> },
                  { label: t("subscriptionTitle"), href: "/subscription", icon: <IconStar /> },
              ]
            : chatAudience === "public"
            ? [
                  { label: t("uploadCv"), href: "/upload", icon: <IconDocument /> },
                  { label: t("subscriptionTitle"), href: "/subscription", icon: <IconStar /> },
              ]
            : [];

    return (
        <>
            <header
                className="relative z-10 border-b border-border-subtle bg-background/80 backdrop-blur-sm"
                dir={isRTL ? "rtl" : "ltr"}
            >
              <div className="relative mx-auto flex w-full max-w-5xl items-center px-3 py-2.5 sm:px-5 lg:px-7">
                {/* Left: hamburger */}
                <div className="flex items-center" style={{ minWidth: 80 }}>
                    {chatAudience === "checking" ? (
                        <span
                            aria-hidden="true"
                            className="h-8 w-8 rounded-lg bg-surface/60 border border-border-subtle animate-pulse motion-reduce:animate-none"
                        />
                    ) : (
                        <button
                            type="button"
                            aria-label={t("openMenu")}
                            aria-expanded={drawerOpen}
                            onClick={() => setDrawerOpen(true)}
                            className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-surface/60 hover:text-text-primary"
                        >
                            <svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden="true">
                                <rect width="18" height="2" rx="1" fill="currentColor" />
                                <rect y="6" width="18" height="2" rx="1" fill="currentColor" />
                                <rect y="12" width="12" height="2" rx="1" fill="currentColor" />
                            </svg>
                        </button>
                    )}
                </div>

                {/* Center: brand */}
                <div className="absolute inset-x-0 flex justify-center pointer-events-none">
                    <Link
                        href="/"
                        className="pointer-events-auto flex items-center gap-1.5 text-text-primary font-black text-[15px] tracking-tight"
                        tabIndex={-1}
                    >
                        <div className="w-6 h-6 rounded-[7px] bg-gold flex items-center justify-center text-[11px] font-black text-[#0a0a1a] shadow-[0_3px_10px_rgba(245,166,35,0.30)]">
                            R
                        </div>
                        Rico<span className="text-gold"> Hunt</span>
                    </Link>
                </div>

                {/* Right side */}
                <div className="flex items-center gap-1 ms-auto" style={{ minWidth: 80, justifyContent: "flex-end" }}>
                    {/* Theme toggle */}
                    <button
                        type="button"
                        onClick={() => setTheme(isDark ? "light" : "dark")}
                        aria-label={isDark ? t("switchToLight") : t("switchToDark")}
                        className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-surface/60 hover:text-text-primary"
                    >
                        {isDark ? <IconSun /> : <IconMoon />}
                    </button>

                    {/* Language toggle */}
                    <button
                        type="button"
                        onClick={() => setLanguage(language === "en" ? "ar" : "en")}
                        aria-label={language === "ar" ? "EN – Switch to English" : "AR – التبديل إلى العربية"}
                        className="h-7 cursor-pointer rounded-md border border-border-subtle px-2 text-[11px] font-medium text-text-muted transition-colors hover:border-border-strong hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50"
                    >
                        {language === "ar" ? "EN" : "AR"}
                    </button>

                    {chatAudience === "authenticated" && (
                        <>
                            {/* New chat */}
                            <button
                                type="button"
                                aria-label={t("newChat")}
                                onClick={onNewChat}
                                className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-surface/60 hover:text-text-primary"
                            >
                                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                                    <path d="M14 1H2C1.45 1 1 1.45 1 2v9c0 .55.45 1 1 1h2v2.5l3.5-2.5H14c.55 0 1-.45 1-1V2c0-.55-.45-1-1-1z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
                                    <path d="M8 5v4M6 7h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                                </svg>
                            </button>

                            {/* Overflow menu */}
                            <div className="relative" ref={overflowRef}>
                                <button
                                    type="button"
                                    aria-label={t("moreOptions")}
                                    aria-expanded={overflowOpen}
                                    onClick={() => setOverflowOpen((o) => !o)}
                                    className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-surface/60 hover:text-text-primary"
                                >
                                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                                        <circle cx="8" cy="2.5" r="1.5" />
                                        <circle cx="8" cy="8" r="1.5" />
                                        <circle cx="8" cy="13.5" r="1.5" />
                                    </svg>
                                </button>

                                {overflowOpen && (
                                    <div
                                        className="absolute top-10 end-0 z-50 w-48 rounded-xl border border-border-subtle bg-surface-elevated/95 backdrop-blur-md shadow-xl py-1"
                                        role="menu"
                                    >
                                        <button
                                            type="button"
                                            role="menuitem"
                                            onClick={() => { onClearChat(); setOverflowOpen(false); }}
                                            className="flex w-full cursor-pointer items-center gap-2.5 px-4 py-2.5 text-[13px] text-text-muted transition-colors hover:bg-surface/60 hover:text-text-primary"
                                        >
                                            <span className="text-text-tertiary"><IconTrash /></span>
                                            {t("clearChat")}
                                        </button>
                                        <Link
                                            href="/archive"
                                            role="menuitem"
                                            onClick={() => setOverflowOpen(false)}
                                            className="flex w-full cursor-pointer items-center gap-2.5 px-4 py-2.5 text-[13px] text-text-muted transition-colors hover:bg-surface/60 hover:text-text-primary"
                                        >
                                            <span className="text-text-tertiary"><IconHistory /></span>
                                            {t("chatHistory")}
                                        </Link>
                                    </div>
                                )}
                            </div>
                        </>
                    )}

                    {/* Public: compact sign in + sign up */}
                    {chatAudience === "public" && (
                        <div className="flex items-center gap-1.5">
                            <Link
                                href={loginHref}
                                className="px-2 text-[12px] text-text-muted transition-colors hover:text-text-primary"
                            >
                                {t("signIn")}
                            </Link>
                            <Link
                                href={signupHref}
                                className="text-[11px] px-2.5 py-1.5 rounded-lg bg-gold text-[#0a0a1a] hover:bg-gold-hover transition-colors font-semibold whitespace-nowrap"
                            >
                                {t("signUp")}
                            </Link>
                        </div>
                    )}

                    {/* Checking skeleton */}
                    {chatAudience === "checking" && (
                        <span
                            aria-hidden="true"
                            className="h-8 w-16 rounded-lg bg-surface/60 border border-border-subtle animate-pulse motion-reduce:animate-none"
                        />
                    )}
                </div>
              </div>
            </header>

            {/* Drawer backdrop */}
            {drawerOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
                    aria-hidden="true"
                    onClick={() => setDrawerOpen(false)}
                />
            )}

            {/* Slide-in drawer */}
            <div
                ref={drawerRef}
                role="dialog"
                aria-label={t("mainMenuLabel")}
                aria-modal="true"
                className={`fixed top-0 z-50 h-full w-72 max-w-[85vw] flex flex-col shadow-[4px_0_40px_rgba(0,0,0,0.5)] transition-transform duration-300 ease-out overflow-hidden ${
                    isRTL ? "right-0" : "left-0"
                } ${
                    drawerOpen ? "translate-x-0" : (isRTL ? "translate-x-full" : "-translate-x-full")
                }`}
                style={{
                    paddingTop: "env(safe-area-inset-top, 0px)",
                    background: "linear-gradient(180deg, #0e0e1f 0%, #0a0a1a 100%)",
                    borderInlineEnd: "1px solid rgba(255,255,255,0.07)",
                }}
            >
                {/* Gold glow at top */}
                <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-gold/[0.07] to-transparent" />

                {/* Drawer header */}
                <div className="relative flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                    <Link
                        href="/"
                        onClick={() => setDrawerOpen(false)}
                        className="flex items-center gap-2 font-black text-[15px] tracking-tight text-white"
                    >
                        <div className="w-7 h-7 rounded-[8px] bg-gold flex items-center justify-center text-[12px] font-black text-[#0a0a1a] shadow-[0_3px_12px_rgba(245,166,35,0.35)]">
                            R
                        </div>
                        Rico<span className="text-gold"> Hunt</span>
                    </Link>
                    <button
                        type="button"
                        aria-label={t("close")}
                        onClick={() => setDrawerOpen(false)}
                        className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-white/40 transition-colors hover:bg-white/[0.06] hover:text-white/80"
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                </div>

                {/* User badge — authenticated only */}
                {chatAudience === "authenticated" && (
                    <div className="relative mx-4 mt-4 mb-1 flex items-center gap-3 rounded-2xl px-4 py-3" style={{ background: "rgba(245,166,35,0.07)", border: "1px solid rgba(245,166,35,0.14)" }}>
                        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-gold/30 to-amber-400/10 text-[13px] font-bold text-gold shadow-[0_0_16px_rgba(245,166,35,0.2)]">
                            {userEmail ? userEmail[0].toUpperCase() : "?"}
                        </div>
                        <div className="min-w-0">
                            <p className="text-[12px] font-semibold text-white/90 truncate">{userEmail ?? (language === "ar" ? "حساب نشط" : "Active account")}</p>
                            <p className="text-[10px] text-white/40 uppercase tracking-[0.12em]">{language === "ar" ? "حساب نشط" : "Active account"}</p>
                        </div>
                        <span className="ms-auto flex h-2 w-2 flex-shrink-0 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(74,222,128,0.8)]" aria-hidden="true" />
                    </div>
                )}

                {/* Drawer nav */}
                <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5" style={{ scrollbarWidth: "none" }}>
                    {/* Section: Navigate */}
                    {drawerItems.length > 0 && (
                        <>
                            <p className="px-3 pb-1.5 pt-2 text-[9px] font-bold uppercase tracking-[0.18em] text-white/25">
                                {language === "ar" ? "التنقل" : "Navigate"}
                            </p>
                            {drawerItems.map((item) => {
                                const isActive = pathname === item.href;
                                return (
                                    <Link
                                        key={item.href}
                                        href={item.href}
                                        onClick={() => setDrawerOpen(false)}
                                        className={cn(
                                            "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-medium transition-all duration-150 cursor-pointer",
                                            isActive
                                                ? "text-gold bg-gold/10"
                                                : "text-white/60 hover:text-white/90 hover:bg-white/[0.05]"
                                        )}
                                    >
                                        {isActive && (
                                            <span aria-hidden="true" className={cn("absolute top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-full bg-gold shadow-[0_0_8px_rgba(245,166,35,0.6)]", isRTL ? "right-0" : "left-0")} />
                                        )}
                                        <span className={cn("flex-shrink-0 transition-colors", isActive ? "text-gold" : "text-white/35 group-hover:text-white/60")}>
                                            {item.icon}
                                        </span>
                                        {item.label}
                                    </Link>
                                );
                            })}
                        </>
                    )}

                    {/* Divider + Section: Preferences */}
                    <div className="my-3" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }} />
                    <p className="px-3 pb-1.5 text-[9px] font-bold uppercase tracking-[0.18em] text-white/25">
                        {language === "ar" ? "التفضيلات" : "Preferences"}
                    </p>

                    <button
                        type="button"
                        onClick={() => setLanguage(language === "en" ? "ar" : "en")}
                        className="group flex w-full cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-medium text-white/60 transition-all hover:bg-white/[0.05] hover:text-white/90"
                    >
                        <span className="flex-shrink-0 text-white/35 group-hover:text-white/60 transition-colors"><IconGlobe /></span>
                        {language === "ar" ? "English" : "العربية"}
                    </button>

                    <button
                        type="button"
                        onClick={() => setTheme(isDark ? "light" : "dark")}
                        className="group flex w-full cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-medium text-white/60 transition-all hover:bg-white/[0.05] hover:text-white/90"
                    >
                        <span className="flex-shrink-0 text-white/35 group-hover:text-white/60 transition-colors">{isDark ? <IconSun /> : <IconMoon />}</span>
                        {isDark ? t("lightMode") : t("darkMode")}
                    </button>

                    <Link
                        href="/settings"
                        onClick={() => setDrawerOpen(false)}
                        className={cn(
                            "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-medium transition-all cursor-pointer",
                            pathname === "/settings"
                                ? "text-gold bg-gold/10"
                                : "text-white/60 hover:text-white/90 hover:bg-white/[0.05]"
                        )}
                    >
                        {pathname === "/settings" && (
                            <span aria-hidden="true" className="absolute start-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-full bg-gold shadow-[0_0_8px_rgba(245,166,35,0.6)]" />
                        )}
                        <span className={cn("flex-shrink-0 transition-colors", pathname === "/settings" ? "text-gold" : "text-white/35 group-hover:text-white/60")}>
                            <IconSettings />
                        </span>
                        {t("settings")}
                    </Link>
                </nav>

                {/* Auth footer */}
                <div className="relative px-4 py-4" style={{ borderTop: "1px solid rgba(255,255,255,0.06)", paddingBottom: "max(1rem, env(safe-area-inset-bottom, 0px))" }}>
                    {chatAudience === "authenticated" ? (
                        <button
                            type="button"
                            onClick={() => { setDrawerOpen(false); onLogout(); }}
                            className="flex w-full cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-medium text-rose-400/80 transition-all hover:bg-rose-500/[0.08] hover:text-rose-400"
                        >
                            <span className="flex-shrink-0 text-rose-400/60"><IconLogout /></span>
                            {t("logout")}
                        </button>
                    ) : chatAudience === "public" ? (
                        <div className="flex flex-col gap-2">
                            <Link
                                href={signupHref}
                                onClick={() => setDrawerOpen(false)}
                                className="flex w-full items-center justify-center rounded-xl px-3 py-2.5 text-[13px] font-bold bg-gold text-[#0a0a1a] hover:bg-gold-hover transition-colors shadow-[0_4px_16px_rgba(245,166,35,0.25)]"
                            >
                                {t("signUpFree")}
                            </Link>
                            <Link
                                href={loginHref}
                                onClick={() => setDrawerOpen(false)}
                                className="flex w-full items-center justify-center rounded-xl px-3 py-2 text-[13px] text-white/50 transition-colors hover:text-white/80"
                            >
                                {t("signIn")}
                            </Link>
                        </div>
                    ) : null}
                </div>
            </div>
        </>
    );
}
