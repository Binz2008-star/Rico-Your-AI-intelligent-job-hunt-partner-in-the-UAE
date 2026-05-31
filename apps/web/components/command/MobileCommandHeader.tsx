"use client";

import { useLanguage } from "@/contexts/LanguageContext";
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
            {/* Header bar */}
            <header
                className="relative z-10 flex items-center px-3 py-2.5 border-b border-border-subtle bg-[#0a0a1a]/80 backdrop-blur-sm"
                dir={isRTL ? "rtl" : "ltr"}
            >
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
                        className="pointer-events-auto flex items-center gap-1.5 text-white font-black text-[15px] tracking-tight"
                        tabIndex={-1}
                    >
                        <div className="w-6 h-6 rounded-[7px] bg-[#f5a623] flex items-center justify-center text-[11px] font-black text-[#0a0a1a] shadow-[0_3px_10px_rgba(245,166,35,0.35)]">
                            R
                        </div>
                        Rico<span className="text-[#f5a623]"> Hunt</span>
                    </Link>
                </div>

                {/* Right side — content depends on auth state */}
                <div className="flex items-center gap-1 ms-auto" style={{ minWidth: 80, justifyContent: "flex-end" }}>
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
                                        className={`absolute top-10 ${isRTL ? "left-0" : "right-0"} z-50 w-48 rounded-xl border border-border-subtle bg-[#13132a]/95 backdrop-blur-md shadow-xl py-1`}
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
                                            href="/command/history"
                                            role="menuitem"
                                            onClick={() => setOverflowOpen(false)}
                                            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-[13px] text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                                        >
                                            <span aria-hidden="true">📜</span>
                                            {language === "ar" ? "تاريخ المحادثات" : "Chat history"}
                                        </Link>
                                        <div className="my-1 border-t border-border-subtle" />
                                        <Link
                                            href="/help"
                                            role="menuitem"
                                            onClick={() => setOverflowOpen(false)}
                                            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-[13px] text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                                        >
                                            <span aria-hidden="true">❓</span>
                                            {language === "ar" ? "مساعدة" : "Help"}
                                        </Link>
                                        <Link
                                            href="/report"
                                            role="menuitem"
                                            onClick={() => setOverflowOpen(false)}
                                            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-[13px] text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                                        >
                                            <span aria-hidden="true">🚩</span>
                                            {language === "ar" ? "الإبلاغ عن مشكلة" : "Report issue"}
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
                className={`fixed top-0 z-50 h-full w-72 max-w-[85vw] bg-[#0d0d1f] border-border-subtle flex flex-col shadow-2xl transition-transform duration-300 ease-out safe-top ${
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
                        className="flex items-center gap-2 text-white font-black text-[15px] tracking-tight"
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

                    {/* Language toggle */}
                    <div className="my-2 border-t border-border-subtle" />
                    <button
                        type="button"
                        onClick={() => setLanguage(language === "en" ? "ar" : "en")}
                        className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-[14px] text-text-muted hover:text-white hover:bg-surface/60 transition-colors"
                    >
                        <span className="text-[16px] w-5 text-center" aria-hidden="true">🌐</span>
                        {language === "ar" ? "English" : "العربية"}
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
