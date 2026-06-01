"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { useTheme } from "@/contexts/ThemeContext";
import Link from "next/link";
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
    const isDark = resolvedTheme === "dark";
    const isRTL = language === "ar";

    const [drawerOpen, setDrawerOpen] = useState(false);
    const [overflowOpen, setOverflowOpen] = useState(false);
    const overflowRef = useRef<HTMLDivElement>(null);
    const drawerRef = useRef<HTMLDivElement>(null);

    // Lock body scroll while drawer is open
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

    // Close overflow on outside click
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

    // Close drawer on outside click
    useEffect(() => {
        if (!drawerOpen) return;
        function handle(e: MouseEvent) {
            if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
                setDrawerOpen(false);
            }
        }
        document.addEventListener("mousedown", handle);
        return () => document.removeEventListener("mousedown", handle);
    }, [drawerOpen]);

    const drawerItems =
        chatAudience === "authenticated"
            ? [
                  { label: language === "ar" ? "الملف الشخصي" : "Profile", href: "/profile", icon: "👤" },
                  { label: language === "ar" ? "رفع السيرة الذاتية" : "Upload CV", href: "/upload", icon: "📄" },
                  { label: language === "ar" ? "الطلبات" : "Applications", href: "/flow", icon: "📋" },
                  { label: language === "ar" ? "الاشتراك" : "Subscription", href: "/subscription", icon: "✦" },
              ]
            : chatAudience === "public"
            ? [
                  { label: language === "ar" ? "رفع السيرة الذاتية" : "Upload CV", href: "/upload", icon: "📄" },
                  { label: language === "ar" ? "الاشتراك" : "Subscription", href: "/subscription", icon: "✦" },
              ]
            : [];

    return (
        <>
            {/* Header bar — full-width divider/background, content aligned to the
                same centred column as the chat body so desktop doesn't pin the
                brand/icons to the far screen edges (#325). */}
            <header
                className="relative z-10 border-b border-border-subtle bg-background/80 backdrop-blur-sm"
                dir={isRTL ? "rtl" : "ltr"}
            >
              <div className="relative flex items-center w-full max-w-3xl mx-auto px-3 py-2.5">
                {/* Left: hamburger */}
                <div className="relative z-10 flex items-center" style={{ minWidth: 80 }}>
                    {chatAudience === "checking" ? (
                        <span
                            aria-hidden="true"
                            className="h-8 w-8 rounded-lg bg-surface/60 border border-border-subtle animate-pulse motion-reduce:animate-none"
                        />
                    ) : (
                        <button
                            type="button"
                            aria-label={language === "ar" ? "فتح القائمة" : "Open menu"}
                            aria-expanded={drawerOpen}
                            onClick={() => setDrawerOpen(true)}
                            className="flex h-8 w-8 items-center justify-center rounded-lg text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                        >
                            <svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden="true">
                                <rect width="18" height="2" rx="1" fill="currentColor" />
                                <rect y="6" width="18" height="2" rx="1" fill="currentColor" />
                                <rect y="12" width="12" height="2" rx="1" fill="currentColor" />
                            </svg>
                        </button>
                    )}
                </div>

                {/* Center: brand (absolute so it's always truly centred) */}
                <div className="absolute inset-x-0 flex justify-center pointer-events-none">
                    <Link
                        href="/"
                        className="pointer-events-auto flex items-center gap-1.5 text-text-primary font-black text-[15px] tracking-tight"
                        tabIndex={-1}
                    >
                        <div className="w-6 h-6 rounded-[7px] bg-[#f5a623] flex items-center justify-center text-[11px] font-black text-[#0a0a1a] shadow-[0_3px_10px_rgba(245,166,35,0.35)]">
                            R
                        </div>
                        Rico<span className="text-[#f5a623]"> Hunt</span>
                    </Link>
                </div>

                {/* Right side — content depends on auth state */}
                <div className="relative z-10 flex items-center gap-1 ms-auto" style={{ minWidth: 80, justifyContent: "flex-end" }}>
                    {/* Theme toggle — always visible */}
                    <button
                        type="button"
                        onClick={() => setTheme(isDark ? "light" : "dark")}
                        aria-label={isDark ? (language === "ar" ? "تبديل إلى الوضع الفاتح" : "Switch to light mode") : (language === "ar" ? "تبديل إلى الوضع الداكن" : "Switch to dark mode")}
                        className="flex h-8 w-8 items-center justify-center rounded-lg text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                    >
                        {isDark ? (
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <circle cx="12" cy="12" r="4" />
                                <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
                            </svg>
                        ) : (
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                            </svg>
                        )}
                    </button>

                    {/* Language toggle — always visible */}
                    <button
                        type="button"
                        onClick={() => setLanguage(language === "en" ? "ar" : "en")}
                        aria-label={language === "ar" ? "EN – Switch to English" : "AR – التبديل إلى العربية"}
                        className="h-7 px-2 rounded-md border border-border-subtle text-[11px] font-medium text-text-muted hover:text-white hover:border-border-strong transition-colors"
                    >
                        {language === "ar" ? "EN" : "AR"}
                    </button>

                    {chatAudience === "authenticated" && (
                        <>
                            {/* New chat */}
                            <button
                                type="button"
                                aria-label={language === "ar" ? "محادثة جديدة" : "New chat"}
                                onClick={onNewChat}
                                className="flex h-8 w-8 items-center justify-center rounded-lg text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
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
                                    aria-label={language === "ar" ? "المزيد" : "More"}
                                    aria-expanded={overflowOpen}
                                    onClick={() => setOverflowOpen((o) => !o)}
                                    className="flex h-8 w-8 items-center justify-center rounded-lg text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                                >
                                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                                        <circle cx="8" cy="2.5" r="1.5" />
                                        <circle cx="8" cy="8" r="1.5" />
                                        <circle cx="8" cy="13.5" r="1.5" />
                                    </svg>
                                </button>

                                {overflowOpen && (
                                    <div
                                        className={`absolute top-10 ${isRTL ? "left-0" : "right-0"} z-50 w-48 rounded-xl border border-border-subtle bg-surface-elevated/95 backdrop-blur-md shadow-xl py-1`}
                                        role="menu"
                                    >
                                        <button
                                            type="button"
                                            role="menuitem"
                                            onClick={() => { onClearChat(); setOverflowOpen(false); }}
                                            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-[13px] text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                                        >
                                            <span aria-hidden="true">🗑</span>
                                            {language === "ar" ? "مسح المحادثة" : "Clear chat"}
                                        </button>
                                        <Link
                                            href="/archive"
                                            role="menuitem"
                                            onClick={() => setOverflowOpen(false)}
                                            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-[13px] text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                                        >
                                            <span aria-hidden="true">📜</span>
                                            {language === "ar" ? "تاريخ المحادثات" : "Chat history"}
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
                                className="text-[12px] text-text-muted hover:text-white transition-colors px-2"
                            >
                                {language === "ar" ? "دخول" : "Sign in"}
                            </Link>
                            <Link
                                href={signupHref}
                                className="text-[11px] px-2.5 py-1.5 rounded-lg bg-magenta text-white hover:bg-magenta-hover transition-colors font-medium whitespace-nowrap"
                            >
                                {language === "ar" ? "سجّل" : "Sign up"}
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
                    className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
                    aria-hidden="true"
                    onClick={() => setDrawerOpen(false)}
                />
            )}

            {/* Slide-in drawer */}
            <div
                ref={drawerRef}
                role="dialog"
                aria-label={language === "ar" ? "القائمة الرئيسية" : "Main menu"}
                aria-modal="true"
                className={`fixed top-0 z-50 h-full w-72 max-w-[85vw] bg-surface border-border-subtle flex flex-col shadow-2xl transition-transform duration-300 ease-out safe-top ${
                    isRTL
                        ? `left-0 border-e ${drawerOpen ? "translate-x-0" : "-translate-x-full"}`
                        : `left-0 border-r ${drawerOpen ? "translate-x-0" : "-translate-x-full"}`
                }`}
                style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}
            >
                {/* Drawer header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
                    <Link
                        href="/"
                        onClick={() => setDrawerOpen(false)}
                        className="flex items-center gap-2 text-text-primary font-black text-[15px] tracking-tight"
                    >
                        <div className="w-6 h-6 rounded-[7px] bg-[#f5a623] flex items-center justify-center text-[11px] font-black text-[#0a0a1a]">
                            R
                        </div>
                        Rico<span className="text-[#f5a623]"> Hunt</span>
                    </Link>
                    <button
                        type="button"
                        aria-label={language === "ar" ? "إغلاق" : "Close"}
                        onClick={() => setDrawerOpen(false)}
                        className="flex h-8 w-8 items-center justify-center rounded-lg text-text-muted hover:text-white hover:bg-surface/60 transition-colors text-lg"
                    >
                        ×
                    </button>
                </div>

                {/* Drawer nav */}
                <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
                    {drawerItems.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
                            onClick={() => setDrawerOpen(false)}
                            className="flex items-center gap-3 rounded-xl px-3 py-3 text-[14px] text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                        >
                            <span className="text-[16px] w-5 text-center" aria-hidden="true">{item.icon}</span>
                            {item.label}
                        </Link>
                    ))}

                    {/* Language + theme toggles */}
                    <div className="my-2 border-t border-border-subtle" />
                    <button
                        type="button"
                        onClick={() => setLanguage(language === "en" ? "ar" : "en")}
                        className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-[14px] text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                    >
                        <span className="text-[16px] w-5 text-center" aria-hidden="true">🌐</span>
                        {language === "ar" ? "English" : "العربية"}
                    </button>
                    <button
                        type="button"
                        onClick={() => setTheme(isDark ? "light" : "dark")}
                        className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-[14px] text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                    >
                        <span className="text-[16px] w-5 text-center" aria-hidden="true">{isDark ? "☀️" : "🌙"}</span>
                        {isDark
                            ? (language === "ar" ? "الوضع الفاتح" : "Light mode")
                            : (language === "ar" ? "الوضع الداكن" : "Dark mode")
                        }
                    </button>

                    <Link
                        href="/settings"
                        onClick={() => setDrawerOpen(false)}
                        className="flex items-center gap-3 rounded-xl px-3 py-3 text-[14px] text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                    >
                        <span className="text-[16px] w-5 text-center" aria-hidden="true">⚙</span>
                        {language === "ar" ? "الإعدادات" : "Settings"}
                    </Link>
                </nav>

                {/* Auth section at bottom */}
                <div className="border-t border-border-subtle px-3 py-4" style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom, 0px))" }}>
                    {chatAudience === "authenticated" ? (
                        <button
                            type="button"
                            onClick={() => { setDrawerOpen(false); onLogout(); }}
                            className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-[14px] text-[#ff5e5b] hover:bg-[rgba(255,94,91,0.08)] transition-colors"
                        >
                            <span className="text-[16px] w-5 text-center" aria-hidden="true">→</span>
                            {language === "ar" ? "تسجيل الخروج" : "Sign out"}
                        </button>
                    ) : chatAudience === "public" ? (
                        <div className="flex flex-col gap-2">
                            <Link
                                href={signupHref}
                                onClick={() => setDrawerOpen(false)}
                                className="flex w-full items-center justify-center rounded-xl px-3 py-2.5 text-[13px] font-semibold bg-magenta text-white hover:bg-magenta-hover transition-colors"
                            >
                                {language === "ar" ? "سجّل مجانًا" : "Sign up free"}
                            </Link>
                            <Link
                                href={loginHref}
                                onClick={() => setDrawerOpen(false)}
                                className="flex w-full items-center justify-center rounded-xl px-3 py-2.5 text-[13px] text-text-muted hover:text-white transition-colors"
                            >
                                {language === "ar" ? "تسجيل الدخول" : "Sign in"}
                            </Link>
                        </div>
                    ) : null}
                </div>
            </div>
        </>
    );
}
