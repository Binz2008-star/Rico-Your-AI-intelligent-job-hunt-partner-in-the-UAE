import type { ReactNode } from "react";
import { noindexMetadata } from "@/lib/seo";

// Auth utility route — crawlable (robots allow) but noindex so search engines
// can see the directive and drop it from the index. (#1064)
export const metadata = noindexMetadata;

export default function NoindexLayout({ children }: { children: ReactNode }) {
    return <>{children}</>;
}
