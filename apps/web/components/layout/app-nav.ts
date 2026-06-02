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

export const mainNavSections: NavSection[] = [
  {
    title: "Execute",
    items: [
      { label: "Command", href: "/command", icon: "auto_awesome" },
      { label: "Jobs", href: "/jobs", icon: "work" },
      { label: "Flow", href: "/flow", icon: "waves" },
    ],
  },
  {
    title: "Intelligence",
    items: [
      { label: "Signals", href: "/signals", icon: "insights" },
      { label: "Saved", href: "/saved-searches", icon: "bookmark" },
      { label: "Archive", href: "/archive", icon: "history" },
    ],
  },
  {
    title: "Account",
    items: [
      { label: "Profile", href: "/profile", icon: "person" },
      { label: "Settings", href: "/settings", icon: "settings" },
      { label: "Subscription", href: "/subscription", icon: "workspace_premium" },
    ],
  },
];

export const utilityNavItems: NavItem[] = [
  { label: "Upload CV", href: "/upload", icon: "upload_file" },
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
