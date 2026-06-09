// App navigation configuration — career-workflow IA
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

// Active routes only — /jobs, /signals, /archive, /saved-searches redirect to /command or /profile

export const mainNavSections: NavSection[] = [
    {
        title: "Search",
        items: [
            { label: "Ask Rico",    href: "/command", icon: "auto_awesome"    },
            { label: "Pipeline",    href: "/flow",    icon: "insights"        },
            { label: "Applications", href: "/queue",   icon: "rocket_launch"   },
        ],
    },
    {
        title: "Career",
        items: [
            { label: "Profile", href: "/profile", icon: "person"      },
            { label: "My Files", href: "/upload",  icon: "folder_open" },
        ],
    },
    {
        title: "Account",
        items: [
            { label: "Pro Plan", href: "/subscription", icon: "workspace_premium" },
            { label: "Settings", href: "/settings",     icon: "settings"          },
        ],
    },
];

export const utilityNavItems: NavItem[] = [];

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
