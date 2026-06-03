// App navigation configuration for Pulse-inspired shell
// Icons use MaterialIcon names for consistency

export interface NavItem {
    label: string;
    href: string;
    icon: string;
    badge?: string;
}

export interface NavSection {
    title: string;
    items: NavItem[];
}

// Phase 3: Navigation configured for active routes only
// Redirected routes excluded per next.config.js:
// /jobs, /signals, /archive, /saved-searches, /settings -> /profile or /command

export const mainNavSections: NavSection[] = [
    {
        title: "Core",
        items: [
            { label: "Command", href: "/command", icon: "auto_awesome" },
            { label: "Flow", href: "/flow", icon: "waves" },
        ],
    },
    {
        title: "Account",
        items: [
            { label: "Profile", href: "/profile", icon: "person" },
            { label: "Subscription", href: "/subscription", icon: "workspace_premium" },
        ],
    },
];

export const utilityNavItems: NavItem[] = [
    { label: "Upload CV", href: "/upload", icon: "upload_file" },
    { label: "Settings", href: "/settings", icon: "settings" },
];

// Navigation metadata for external linking
export const navMeta = {
    brand: {
        name: "Rico",
        shortName: "R",
        tagline: "AI Job Hunt Partner",
    },
    status: {
        label: "System live",
        region: "UAE",
        color: "#00c9a7" as const,
    },
};
