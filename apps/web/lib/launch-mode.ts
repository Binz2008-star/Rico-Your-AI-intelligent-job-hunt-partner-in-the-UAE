export type LaunchMode = "live" | "waitlist";

/**
 * Server-side launch mode. Missing/invalid values preserve the current live
 * product so a merge cannot silently shut production down.
 */
export function getLaunchMode(): LaunchMode {
  return process.env.RICO_LAUNCH_MODE?.trim().toLowerCase() === "waitlist"
    ? "waitlist"
    : "live";
}

export function isWaitlistMode(): boolean {
  return getLaunchMode() === "waitlist";
}
