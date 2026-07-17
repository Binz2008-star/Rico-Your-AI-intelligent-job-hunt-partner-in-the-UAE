import type { ReactNode } from "react";
import { noindexMetadata } from "@/lib/seo";

// Internal/app surface — route-level noindex (client page can't export metadata). (#1064)
export const metadata = noindexMetadata;

export default function NoindexLayout({ children }: { children: ReactNode }) {
    return <>{children}</>;
}
