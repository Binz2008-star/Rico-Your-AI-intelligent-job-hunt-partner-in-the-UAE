"use client";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";

interface AppShellProps {
  children: React.ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
  sidebarProps?: React.ComponentProps<typeof AppSidebar>;
  topbarProps?: Omit<React.ComponentProps<typeof AppTopbar>, "title" | "subtitle">;
  showSidebar?: boolean;
  showTopbar?: boolean;
}

export function AppShell({
  children,
  className,
  title,
  subtitle,
  sidebarProps,
  topbarProps,
  showSidebar = true,
  showTopbar = true,
}: AppShellProps) {
  return (
    <div className={cn("flex h-screen w-full overflow-hidden bg-background", className)}>
      {/* Sidebar */}
      {showSidebar && <AppSidebar {...sidebarProps} />}

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Topbar */}
        {showTopbar && (
          <AppTopbar title={title} subtitle={subtitle} {...topbarProps} />
        )}

        {/* Scrollable Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto max-w-6xl">
            <Card className="min-h-[calc(100vh-12rem)] border-0 bg-transparent shadow-none">
              {children}
            </Card>
          </div>
        </main>
      </div>
    </div>
  );
}
