import type { TrajectoryForecast } from "@/lib/api/orchestration";

const TRAJECTORY_ANALYSIS_RE =
    /\b(analyse|analyze|map|show|review|assess)\b[^.?!]*\b(career|trajector(?:y|ies)|next (?:career )?move)\b/i;

export function looksLikeTrajectoryAnalysis(message: string): boolean {
    return TRAJECTORY_ANALYSIS_RE.test(message);
}

export function formatTrajectory(forecast: TrajectoryForecast): string {
    const lines: string[] = ["Here's your current career trajectory, built from your live Rico profile:", ""];
    forecast.nodes.forEach((node, index) => {
        const confidence = Math.round(node.probability * 100);
        const marker = node.status === "completed" ? "✓" : node.status === "current" ? "▶" : "○";
        lines.push(`${marker} **${index + 1}. ${node.title}** _(${node.timeline})_`);
        lines.push(`   ${node.description}`);
        lines.push(`   Confidence: ${confidence}%`);
        lines.push("");
    });
    lines.push("Ask me to map your next move, evaluate an opportunity, or search roles that fit this path.");
    return lines.join("\n");
}
