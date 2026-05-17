"use client";

import { useAuth } from "@/hooks/useAuth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function HomePage() {
    const router = useRouter();
    const { user, ready } = useAuth();

    useEffect(() => {
        if (!ready) return;
        // If user is authenticated, redirect to orchestration
        // If not authenticated, stay on landing page (do not redirect to /upload)
        if (user) {
            router.push('/orchestrate');
        }
    }, [ready, user, router]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-background">
            <div className="text-center">
                <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-on-surface-variant">Initializing Rico AI...</p>
            </div>
        </div>
    );
}
