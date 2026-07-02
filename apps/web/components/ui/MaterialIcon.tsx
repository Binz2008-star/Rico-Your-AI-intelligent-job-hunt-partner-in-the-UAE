import { cn } from '@/lib/utils';
import React from 'react';

interface MaterialIconProps extends React.SVGAttributes<SVGSVGElement> {
    icon: string;
    filled?: boolean;
    weight?: 100 | 200 | 300 | 400 | 500 | 600 | 700;
    size?: number;
}

type IconRenderer = (filled: boolean) => React.ReactNode;

const ICONS: Record<string, IconRenderer> = {
    account_circle: () => (
        <>
            <circle cx="12" cy="12" r="9" />
            <circle cx="12" cy="10" r="3" />
            <path d="M6.8 18.2a6.2 6.2 0 0 1 10.4 0" />
        </>
    ),
    add: () => (
        <>
            <path d="M12 5v14" />
            <path d="M5 12h14" />
        </>
    ),
    arrow_forward: () => (
        <>
            <path d="M5 12h12" />
            <path d="m13 6 6 6-6 6" />
        </>
    ),
    auto_awesome: (filled) => (
        <>
            <path d="m12 3 1.8 4.5L18 9.3l-4.2 1.8L12 16l-1.8-4.9L6 9.3l4.2-1.8L12 3Z" fill={filled ? 'currentColor' : 'none'} />
            <path d="m19 5 .7 1.8L21.5 7.5l-1.8.7L19 10l-.7-1.8-1.8-.7 1.8-.7L19 5Z" fill={filled ? 'currentColor' : 'none'} />
            <path d="m5 14 .8 2 2 .8-2 .8L5 20l-.8-2-2-.8 2-.8L5 14Z" fill={filled ? 'currentColor' : 'none'} />
        </>
    ),
    bookmark: (filled) => (
        <path d="M6 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v17l-6-4-6 4V4Z" fill={filled ? 'currentColor' : 'none'} />
    ),
    business: () => (
        <>
            <path d="M4 20h16" />
            <path d="M6 20V7l6-3 6 3v13" />
            <path d="M9 10h.01" />
            <path d="M15 10h.01" />
            <path d="M9 14h.01" />
            <path d="M15 14h.01" />
        </>
    ),
    chat: () => (
        <path d="M21 11.5a8.5 8.5 0 0 1-12.5 7.5L3 20.5l1.5-5.5A8.5 8.5 0 1 1 21 11.5Z" />
    ),
    close: () => (
        <path d="M18 6 6 18M6 6l12 12" />
    ),
    edit: () => (
        <>
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
            <path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4Z" />
        </>
    ),
    task_alt: () => (
        <>
            <path d="M9 12.5 11.5 15 15 10" />
            <path d="M20.8 14a9 9 0 1 1-6.8-10.8" />
        </>
    ),
    check_circle: () => (
        <>
            <circle cx="12" cy="12" r="9" />
            <path d="m8.5 12 2.2 2.2 4.8-4.8" />
        </>
    ),
    radio_button_unchecked: () => (
        <circle cx="12" cy="12" r="9" />
    ),
    chevron_right: () => (
        <path d="m9 6 6 6-6 6" />
    ),
    dark_mode: (filled) => (
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" fill={filled ? 'currentColor' : 'none'} />
    ),
    dashboard: () => (
        <>
            <rect x="3" y="3" width="7" height="9" rx="1" />
            <rect x="14" y="3" width="7" height="5" rx="1" />
            <rect x="14" y="12" width="7" height="9" rx="1" />
            <rect x="3" y="16" width="7" height="5" rx="1" />
        </>
    ),
    desktop_windows: () => (
        <>
            <rect x="3" y="4" width="18" height="12" rx="2" />
            <path d="M8 20h8" />
            <path d="M12 16v4" />
        </>
    ),
    error_outline: () => (
        <>
            <circle cx="12" cy="12" r="9" />
            <path d="M12 8v4" />
            <path d="M12 16h.01" />
        </>
    ),
    folder_open: () => (
        <>
            <path d="M4 7a2 2 0 0 1 2-2h3l2 2h7a2 2 0 0 1 2 2v1" />
            <path d="m3.4 11.2 1.7 7a1.5 1.5 0 0 0 1.5 1.1h11.6a1.5 1.5 0 0 0 1.5-1.1l1.5-7A1 1 0 0 0 22.7 10H4.4a1 1 0 0 0-1 1.2Z" />
        </>
    ),
    history: () => (
        <>
            <path d="M4.5 11a7.5 7.5 0 1 1 2.2 5.3" />
            <path d="M4.5 7.5V11H8" />
            <path d="M12 8.5V12l2.5 1.5" />
        </>
    ),
    hourglass_empty: () => (
        <>
            <path d="M7 4h10" />
            <path d="M7 20h10" />
            <path d="M8 4c0 3 1.8 4.5 4 6 2.2 1.5 4 3 4 6" />
            <path d="M16 4c0 3-1.8 4.5-4 6-2.2 1.5-4 3-4 6" />
        </>
    ),
    insights: () => (
        <>
            <path d="M5 18V9" />
            <path d="M10 18V6" />
            <path d="M15 18v-4" />
            <path d="M20 18V8" />
            <path d="m5 13 5-4 5 2 5-5" />
        </>
    ),
    light_mode: () => (
        <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </>
    ),
    lock: () => (
        <>
            <rect x="6.5" y="11" width="11" height="8" rx="2" />
            <path d="M9 11V8.8a3 3 0 1 1 6 0V11" />
        </>
    ),
    lock_reset: () => (
        <>
            <rect x="5" y="11" width="14" height="9" rx="2" />
            <path d="M8 11V8a4 4 0 0 1 7.7-1.5" />
            <path d="M16.5 4v2.5H14" />
        </>
    ),
    login: () => (
        <>
            <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
            <path d="m10 17 5-5-5-5" />
            <path d="M15 12H3" />
        </>
    ),
    logout: () => (
        <>
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <path d="m16 17 5-5-5-5" />
            <path d="M21 12H9" />
        </>
    ),
    mark_email_unread: () => (
        <>
            <path d="M20 9.5V18a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h8" />
            <path d="m4 7 8 5.5 3-2" />
            <circle cx="19" cy="5" r="2.5" />
        </>
    ),
    person: () => (
        <>
            <circle cx="12" cy="8" r="4" />
            <path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
        </>
    ),
    refresh: () => (
        <>
            <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
            <path d="M21 3v5h-5" />
            <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
            <path d="M3 21v-5h5" />
        </>
    ),
    rocket_launch: () => (
        <>
            <path d="M13 4c2.5.6 4.4 2.5 5 5L13 14c-2.5-.6-4.4-2.5-5-5l5-5Z" />
            <path d="M9 15 5 19" />
            <path d="M14 10a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4Z" />
            <path d="m7 17-2 2" />
        </>
    ),
    send: () => (
        <>
            <path d="M22 2 11 13" />
            <path d="M22 2 15 22l-4-9-9-4 20-7Z" />
        </>
    ),
    settings: () => (
        <>
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
        </>
    ),
    upload_file: () => (
        <>
            <path d="M14 3H8a2 2 0 0 0-2 2v14h12V9l-4-6Z" />
            <path d="M14 3v6h6" />
            <path d="m12 16 0-6" />
            <path d="m9.5 12.5 2.5-2.5 2.5 2.5" />
        </>
    ),
    warning: () => (
        <>
            <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h16.9a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
            <path d="M12 9v4" />
            <path d="M12 17h.01" />
        </>
    ),
    waves: () => (
        <>
            <path d="M3 13c2.2-2 4.3-2 6.5 0s4.3 2 6.5 0 4.3-2 6.5 0" />
            <path d="M3 17c2.2-2 4.3-2 6.5 0s4.3 2 6.5 0 4.3-2 6.5 0" />
            <path d="M3 9c2.2-2 4.3-2 6.5 0s4.3 2 6.5 0 4.3-2 6.5 0" />
        </>
    ),
    work: () => (
        <>
            <rect x="3" y="7" width="18" height="13" rx="2" />
            <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            <path d="M3 13h18" />
        </>
    ),
    workspace_premium: () => (
        <>
            <circle cx="12" cy="9" r="5" />
            <path d="M8.8 13.2 7 21l5-3 5 3-1.8-7.8" />
        </>
    ),
};

export const MaterialIcon = React.forwardRef<SVGSVGElement, MaterialIconProps>(
    ({ icon, filled = false, weight = 300, size = 24, className, ...props }, ref) => {
        const glyph = ICONS[icon] ?? ICONS.auto_awesome;
        if (process.env.NODE_ENV !== 'production' && !ICONS[icon]) {
            // Surface unmapped icon names instead of silently rendering a sparkle.
            console.warn(`[MaterialIcon] no glyph for "${icon}" — falling back to auto_awesome`);
        }
        const ariaLabel = props['aria-label'];
        return (
            <svg
                ref={ref}
                viewBox="0 0 24 24"
                width={size}
                height={size}
                fill="none"
                stroke="currentColor"
                strokeWidth={Math.max(1.5, weight / 220)}
                strokeLinecap="round"
                strokeLinejoin="round"
                className={cn('inline-block shrink-0', className)}
                aria-hidden={ariaLabel ? undefined : true}
                role={ariaLabel ? 'img' : undefined}
                focusable="false"
                {...props}
            >
                {glyph(filled)}
            </svg>
        );
    }
);

MaterialIcon.displayName = 'MaterialIcon';
