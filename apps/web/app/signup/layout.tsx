import type { Metadata } from "next";
import type { ReactNode } from "react";

// Public acquisition page — self-canonical so it does not inherit the root "/"
// canonical (which would otherwise fold /signup into the home page). (#1064)
export const metadata: Metadata = {
    alternates: { canonical: "/signup" },
};

export default function SignupLayout({ children }: { children: ReactNode }) {
    return <>{children}</>;
}
