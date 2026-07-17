"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquareText,
  User,
  Layers,
  Upload,
  Settings as SettingsIcon,
} from "lucide-react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useLanguage } from "@/contexts/LanguageContext";
import { useAppContent } from "@/lib/app-content";
import { logout } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useState } from "react";

const NAV = [
  { href: "/command", key: "command", Icon: MessageSquareText },
  { href: "/profile", key: "profile", Icon: User },
  { href: "/applications", key: "applications", Icon: Layers },
  { href: "/upload", key: "upload", Icon: Upload },
  { href: "/settings", key: "settings", Icon: SettingsIcon },
] as const;

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const c = useAppContent();
  const { language } = useLanguage();
  const pathname = usePathname();
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  async function handleLogout() {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      router.push("/login");
      setSigningOut(false);
    }
  }

  return (
    <div className="relative z-10 min-h-screen bg-background text-foreground">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 start-0 hidden w-[220px] flex-col border-e border-rule bg-paper/60 backdrop-blur md:flex">
        <div className="flex h-[68px] items-baseline gap-2 border-b border-rule px-5">
          <Link href="/" className="serif text-[20px] leading-none text-ink">
            Rico
          </Link>
          <span className="mono-eyebrow">{c.nav.workspace}</span>
        </div>
        <nav className="flex-1 px-3 py-4">
          <ul className="flex flex-col gap-1">
            {NAV.map(({ href, key, Icon }) => {
              const active = pathname === href || pathname.startsWith(href + "/");
              return (
                <li key={href}>
                  <Link
                    href={href}
                    className={`flex items-center gap-3 rounded-sm px-3 py-2 font-sans text-[13.5px] tracking-tight transition-colors ${
                      active
                        ? "bg-ink text-paper"
                        : "text-ink-mute hover:bg-paper-2 hover:text-ink"
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden />
                    <span>{c.nav[key as keyof typeof c.nav] as string}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="flex items-center gap-2 border-t border-rule px-4 py-3">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </aside>

      {/* Content column */}
      <div className="flex min-h-screen flex-col md:ps-[220px]">
        {/* Mobile top bar */}
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-rule bg-paper/80 px-4 py-3 backdrop-blur md:hidden">
          <Link href="/" className="serif text-[18px] leading-none text-ink">
            Rico
          </Link>
          <span className="mono-eyebrow">{c.nav.workspace}</span>
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            <ThemeToggle />
          </div>
        </header>

        <main className="flex-1 px-5 pt-6 pb-24 md:px-10 md:pt-10 md:pb-16">
          {children}
        </main>

        {/* Mobile bottom nav */}
        <nav
          className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-rule bg-paper/95 backdrop-blur md:hidden"
          aria-label={c.nav.workspace}
        >
          {NAV.map(({ href, key, Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            const label = c.nav[key as keyof typeof c.nav] as string;
            return (
              <Link
                key={href}
                href={href}
                title={label}
                aria-label={label}
                className={`flex min-w-0 flex-col items-center gap-1 px-1 py-2 transition-colors ${
                  active ? "text-ink" : "text-ink-mute"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                <span
                  className={`block w-full truncate text-center text-[10px] leading-none ${
                    language === "ar"
                      ? "font-sans"
                      : "font-mono uppercase tracking-[0.04em]"
                  }`}
                >
                  {label}
                </span>
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="mb-8 grid grid-cols-1 items-end gap-4 border-b border-rule pb-6 sm:grid-cols-[minmax(0,1fr)_auto]">
      <div className="min-w-0">
        <div className="mono-eyebrow">{eyebrow}</div>
        <h1 className="serif mt-2 text-[32px] leading-[1.05] text-ink sm:truncate sm:text-[36px] md:text-[44px]">
          {title}
        </h1>
      </div>
      {children ? <div className="flex flex-wrap items-center gap-2">{children}</div> : null}
    </header>
  );
}

export function DemoBadge() {
  const c = useAppContent();
  return (
    <span className="inline-flex items-center gap-1 border border-rule px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.22em] text-ink-mute">
      {c.common.sample}
    </span>
  );
}
