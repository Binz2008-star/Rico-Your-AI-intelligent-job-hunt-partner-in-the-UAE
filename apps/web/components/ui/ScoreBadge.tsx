import { cn } from "@/lib/utils";

export function ScoreBadge({ score }: { score?: number | null }) {
    if (typeof score !== "number" || score <= 0) return null;
    // Chat endpoint emits 0.0–1.0 floats; /jobs endpoint emits 0–100 integers.
    const pct = Math.min(100, Math.round(score <= 1 ? score * 100 : score));
    if (pct === 0) return null;
    const className =
        pct >= 85
            ? "text-[#00c9a7] bg-[rgba(0,201,167,0.1)] border-[rgba(0,201,167,0.2)]"
            : pct >= 65
                ? "text-ember bg-ember/10 border-ember/20"
                : "text-white/50 bg-white/4 border-white/10";

    return (
        <span
            className={cn(
                "inline-flex items-center px-2.5 py-1 rounded-full text-[13px] font-black border font-['Cabinet_Grotesk',sans-serif] tracking-tight",
                className
            )}
        >
            {pct}%
        </span>
    );
}
