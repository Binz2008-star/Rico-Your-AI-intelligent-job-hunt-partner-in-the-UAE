// Signup attribution capture (issue #922). First-touch UTM/referrer/landing
// data is stashed in sessionStorage on app load and attached to the register
// call, so the backend can report real signup sources instead of a hardcoded
// value. Capture is best-effort: storage failures (private mode) are ignored.

const STORAGE_KEY = "rico_signup_attribution";
const MAX_FIELD_LEN = 300;

export interface SignupAttribution {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  referrer?: string;
  landing_path?: string;
}

const UTM_KEYS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
] as const;

export function getSignupAttribution(): SignupAttribution | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    return typeof parsed === "object" && parsed !== null
      ? (parsed as SignupAttribution)
      : null;
  } catch {
    return null;
  }
}

export function captureSignupAttribution(): void {
  if (typeof window === "undefined") return;
  try {
    const params = new URLSearchParams(window.location.search);
    const utm: SignupAttribution = {};
    for (const key of UTM_KEYS) {
      const value = params.get(key)?.trim();
      if (value) utm[key] = value.slice(0, MAX_FIELD_LEN);
    }
    const hasUtm = Object.keys(utm).length > 0;

    const stored = getSignupAttribution();
    // First touch wins; a later URL carrying explicit UTM params upgrades a
    // stored capture that had none.
    if (stored?.utm_source) return;
    if (stored && !hasUtm) return;

    const attribution: SignupAttribution = { ...(stored ?? {}), ...utm };

    if (!attribution.referrer && document.referrer) {
      try {
        const host = new URL(document.referrer).hostname;
        if (host && host !== window.location.hostname) {
          attribution.referrer = document.referrer.slice(0, MAX_FIELD_LEN);
        }
      } catch {
        // Invalid referrer URL — skip it.
      }
    }
    if (!attribution.landing_path) {
      attribution.landing_path = window.location.pathname.slice(0, MAX_FIELD_LEN);
    }

    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(attribution));
  } catch {
    // sessionStorage unavailable — attribution is best-effort.
  }
}
