"use client";

import { subscribersStrings } from "@/app/admin/subscribers/i18n";
import { useLanguage } from "@/contexts/LanguageContext";
import { fetchMe } from "@/lib/api";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { MaterialIcon } from "../ui/MaterialIcon";

/**
 * Owner-only navigation entry to /admin/subscribers.
 *
 * Renders nothing unless the server-computed `/me.is_owner` flag is true, so a
 * normal user never sees the entry (the route entry is hidden, not merely
 * styled away). Authorization is never decided here — the backend enforces it
 * on every /admin/subscribers request — this only controls visibility.
 */
export function OwnerNavEntry() {
    const { language } = useLanguage();
    const s = subscribersStrings(language);
    const pathname = usePathname();
    const [isOwner, setIsOwner] = useState(false);

    useEffect(() => {
        let alive = true;
        fetchMe()
            .then((me) => {
                if (alive) setIsOwner(Boolean(me.is_owner));
            })
            .catch(() => {
                /* guests / errors: entry stays hidden */
            });
        return () => {
            alive = false;
        };
    }, []);

    if (!isOwner) return null;

    const active = Boolean(pathname && pathname.startsWith("/admin/subscribers"));

    return (
        <div className="px-3 pb-1">
            <Link
                href="/admin/subscribers"
                aria-current={active ? "page" : undefined}
                className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
                    active
                        ? "bg-gold/15 text-gold"
                        : "text-text-secondary hover:bg-surface-subtle hover:text-text-primary",
                )}
            >
                <MaterialIcon icon="group" size={18} className="flex-shrink-0 opacity-70" />
                <span className="flex-1">{s.navSubscribers}</span>
                <span className="rounded-full bg-overlay/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-text-tertiary">
                    {s.ownerOnly}
                </span>
            </Link>
        </div>
    );
}
