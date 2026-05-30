"use client";

import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
    {
        label: "Command",
        href: "/command",
        icon: (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
        ),
    },
    {
        label: "Profile",
        href: "/profile",
        icon: (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
            </svg>
        ),
    },
    {
        label: "Upload",
        href: "/upload",
        icon: (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
        ),
    },
    {
        label: "Subscription",
        href: "/subscription",
        icon: (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
                <line x1="1" y1="10" x2="23" y2="10" />
            </svg>
        ),
    },
];

export function Sidebar() {
    const pathname = usePathname();
    const { user, logout } = useAuth();

    const initials = user?.name
        ? user.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()
        : "R";

    return (
        <aside className="w-[220px] flex-shrink-0 bg-[#0a0a1a] border-r border-white/5 flex flex-col h-full overflow-y-auto">
            {/* Logo */}
            <div className="px-5 py-5 border-b border-white/5 flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-[8px] bg-[#f5a623] flex items-center justify-center text-[#0a0a1a] font-['Cabinet_Grotesk',sans-serif] font-black text-[13px] shadow-[0_4px_12px_rgba(245,166,35,0.35)]">
                    R
                </div>
                <span className="font-['Cabinet_Grotesk',sans-serif] font-800 text-[17px] tracking-tight text-white">
                    Rico <span className="text-[#f5a623]">Hunt</span>
                </span>
            </div>

            {/* Live status */}
            <div className="px-5 py-3 flex items-center gap-2 border-b border-white/5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00c9a7] shadow-[0_0_6px_#00c9a7] animate-pulse" />
                <span className="text-[11px] text-[#00c9a7] font-medium">System live · UAE</span>
            </div>

            {/* Nav */}
            <nav className="flex-1 px-2 py-3 flex flex-col gap-0.5">
                <p className="px-3 pb-2 pt-2 text-[10px] uppercase tracking-widest text-white/25 font-semibold">
                    Navigation
                </p>
                {navItems.map((item) => {
                    const active = pathname === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "flex items-center gap-2.5 px-3 py-2 rounded-[9px] text-[13px] font-medium transition-all duration-150",
                                active
                                    ? "bg-[rgba(245,166,35,0.10)] text-[#f5a623] border border-[rgba(245,166,35,0.22)]"
                                    : "text-white/45 hover:text-white/80 hover:bg-white/5"
                            )}
                        >
                            <span className={cn("flex-shrink-0", active ? "opacity-100" : "opacity-60")}>
                                {item.icon}
                            </span>
                            {item.label}
                        </Link>
                    );
                })}
            </nav>

            {/* User footer */}
            <div className="px-3 py-4 border-t border-white/5">
                <button
                    onClick={logout}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-[9px] hover:bg-white/5 transition-colors group"
                >
                    <div className="w-7 h-7 rounded-full bg-[#f5a623] flex items-center justify-center text-[#0a0a1a] font-['Cabinet_Grotesk',sans-serif] font-black text-[10px] flex-shrink-0">
                        {initials}
                    </div>
                    <div className="flex-1 min-w-0 text-left">
                        <p className="text-[12px] font-medium text-white/70 truncate group-hover:text-white/90">
                            {user?.name ?? "User"}
                        </p>
                        <p className="text-[10px] text-white/30 truncate">{user?.email ?? ""}</p>
                    </div>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="opacity-30 flex-shrink-0">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
                    </svg>
                </button>
            </div>
        </aside>
    );
}
