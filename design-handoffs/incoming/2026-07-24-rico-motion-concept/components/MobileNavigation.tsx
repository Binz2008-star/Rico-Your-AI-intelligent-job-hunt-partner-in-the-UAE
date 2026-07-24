/**
 * MobileNavigation — hamburger + full-screen overlay in the Rico Atelier
 * identity (warm paper, ink, clay — NOT a white agency overlay). Escape closes,
 * focus returns to the toggle, body scroll locks while open, and the overlay is
 * `pointerEvents:none` when hidden. Keep Rico's real product links here.
 */
"use client";
import React, { useEffect, useRef, useState } from "react";

export interface NavLink {
    label: string;
    href: string;
}

export interface MobileNavigationProps {
    links: NavLink[];
    /** authenticated vs guest can swap the trailing CTA. */
    cta?: { label: string; href: string };
    brand?: React.ReactNode;
}

export function MobileNavigation({ links, cta, brand }: MobileNavigationProps) {
    const [open, setOpen] = useState(false);
    const toggleRef = useRef<HTMLButtonElement>(null);

    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") { setOpen(false); toggleRef.current?.focus(); }
        };
        document.addEventListener("keydown", onKey);
        const prev = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
    }, [open]);

    return (
        <div className="md:hidden">
            <button
                ref={toggleRef}
                aria-label={open ? "Close menu" : "Open menu"}
                aria-expanded={open}
                onClick={() => setOpen((o) => !o)}
                className="rico-burger"
            >
                <span data-bar="1" />
                <span data-bar="2" />
                <span data-bar="3" />
            </button>

            <div
                role="dialog"
                aria-modal="true"
                aria-hidden={!open}
                className="rico-mobilenav"
                style={{ opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none" }}
            >
                {brand && <div style={{ marginBottom: 24 }}>{brand}</div>}
                <nav style={{ display: "flex", flexDirection: "column", gap: 24 }}>
                    {links.map((l) => (
                        <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="rico-mobilenav__link">
                            {l.label}
                        </a>
                    ))}
                    {cta && (
                        <a href={cta.href} onClick={() => setOpen(false)} className="rico-mobilenav__cta">
                            {cta.label}
                        </a>
                    )}
                </nav>
            </div>
        </div>
    );
}
