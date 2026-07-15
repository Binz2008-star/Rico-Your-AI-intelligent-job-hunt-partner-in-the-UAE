"use client";

import { AuthGate } from "@/components/auth/AuthGate";
import { QueueAtelier } from "@/components/queue/QueueAtelier";
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
import { useRequireAuth } from "@/hooks/useRequireAuth";

export default function QueuePage() {
    const { user, authorized } = useRequireAuth();

    if (!authorized || !user) {
        return <AuthGate />;
    }

    return (
        <WorkspaceShell>
            <QueueAtelier />
        </WorkspaceShell>
    );
}
