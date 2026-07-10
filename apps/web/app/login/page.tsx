"use client";

import { LoginForm } from '@/components/auth/LoginForm';
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function LoginPageContent() {
    const searchParams = useSearchParams();
    const initialEmail = searchParams.get("email") ?? "";
    return <LoginForm initialEmail={initialEmail} />;
}

export default function LoginPage() {
    return (
        <Suspense>
            <LoginPageContent />
        </Suspense>
    );
}
