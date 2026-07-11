"use client";

import { LoginForm } from '@/components/auth/LoginForm';
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function LoginPageContent() {
    const searchParams = useSearchParams();
    const initialEmail = searchParams.get("email") ?? "";
    const next = searchParams.get("next");
    return <LoginForm initialEmail={initialEmail} next={next} />;
}

export default function LoginPage() {
    return (
        <Suspense>
            <LoginPageContent />
        </Suspense>
    );
}
