"use client";

export function QADebugMarker() {
  // Get build info from environment variables
  const buildCommit = process.env.NEXT_PUBLIC_GIT_COMMIT || "dev";
  const buildTime = process.env.NEXT_PUBLIC_BUILD_TIME || new Date().toISOString();

  return (
    <div
      className="fixed bottom-0 right-0 z-[9999] text-[10px] text-text-muted opacity-50 pointer-events-none"
      style={{ fontSize: "9px", padding: "2px 4px" }}
    >
      {buildCommit.slice(0, 7)}
    </div>
  );
}
