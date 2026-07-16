/**
 * lib/job-fallback.ts
 *
 * Safe fallback actions for job cards whose direct apply/source link is
 * unavailable or degraded (login_required, rate_limited, aggregator_untrusted,
 * google_intermediary, or simply missing from the provider).
 *
 * A job card must NEVER be a dead-end: even when we cannot surface a trusted,
 * directly-clickable apply URL, the user still gets honest, clearly-labelled
 * ways to act — search the role on the company site / Google / LinkedIn, copy
 * the title+company, or save it to their pipeline.
 *
 * Safety: these are user-initiated *search* helpers and clipboard/pipeline
 * actions. They are never presented as a verified "Apply" link, so they do not
 * bypass source-quality gating or fabricate an apply URL. URL construction is
 * pure (no network) and lives here so it can be unit-tested as a regression
 * guard against dead-end cards.
 *
 * employer_url (#721): when JSearch provides the company's own website via the
 * employer_website field, the company-site CTA uses that URL directly instead
 * of constructing a Google search. It is NEVER shown as an "Apply" link and
 * NEVER treated as a verified apply destination.
 */

import type { JobMatch } from "@/lib/api";

/**
 * ── Primary apply-link decision tree (shared, pure, BUG-03 safe) ──────────────
 *
 * `resolveJobLink` is the SINGLE source of truth for which link (if any) a job
 * card surfaces as its primary affordance, and whether that link is trusted.
 * It is used by BOTH the public `JobMatchCard` (app/command/page.tsx) and the
 * authenticated `JobMatchCardAtelier` so the two cards can never drift apart on
 * trust behaviour — most importantly BUG-03: a degraded/untrusted provider link
 * (login_required, rate_limited, aggregator_untrusted, google_intermediary) is
 * NEVER surfaced as a verified "Apply" link. Google-intermediary search URLs
 * are stripped from source/alt so they are never mistaken for a listing page.
 *
 * The resolver returns TRANSLATION KEYS (not display strings) for the label, so
 * it stays pure and locale-independent — each card resolves the key via `t()`.
 * When no clean/trusted link exists, `linkHref` is "" and the card renders the
 * "link unavailable" state plus `getJobFallbackActions` (never a dead-end).
 */

export type VerificationStatus = JobMatch["verification_status"];

/** data-testid for the primary link (empty when no link is surfaced). */
export type JobLinkTestId = "job-link-apply" | "job-link-source" | "job-link-alt" | "";

/** Translation key for the primary link label (empty when no link is surfaced). */
export type JobLinkLabelKey = "cmdApply" | "cmdViewSource" | "cmdApplySearch" | "cmdApplyAlt" | "";

export interface ResolvedJobLink {
  /** Primary link href; "" when no clean/trusted link can be surfaced. */
  linkHref: string;
  /** Translation key for the primary link label; "" when `linkHref` is "". */
  linkLabelKey: JobLinkLabelKey;
  /** data-testid for the primary link; "" when `linkHref` is "". */
  linkTestId: JobLinkTestId;
  /** Cleaned source URL (Google-intermediary stripped); "" when none. */
  sourceUrl: string;
  /** Cleaned alt URL (Google-intermediary stripped); "" when none. */
  altUrl: string;
  /** True when the primary provider link is degraded/untrusted (BUG-03 gate). */
  isBadPrimary: boolean;
  /** Whether to render the secondary "View source" link beside the primary. */
  showSource: boolean;
}

/** Trim a URL, treating the placeholder "#" (and empty) as "no URL". */
function cleanUrl(u?: string): string {
  return u && u !== "#" ? u.trim() : "";
}

/**
 * A Google-intermediary URL is a Google Jobs / Google search result, NOT a
 * direct listing or apply page. These are stripped from source/alt so they are
 * never surfaced as a trusted source link (they only feed the honest
 * "Search"/alt affordance under `google_intermediary`).
 */
export function isGoogleIntermediary(u: string): boolean {
  if (!u) return false;
  try {
    const p = new URL(u);
    const h = p.hostname.replace(/^www\./, "");
    return h === "jobs.google.com" || (h === "google.com" && p.pathname.includes("/search"));
  } catch {
    return false;
  }
}

/**
 * Resolve the primary apply/source/alt link for a job card.
 *
 * Decision order (identical to the historical per-card logic, now shared):
 *   1. clean `apply_url` + trusted primary  → Apply           (job-link-apply)
 *   2. clean `source_url` + trusted primary → View source     (job-link-source)
 *   3. `google_intermediary` + alt          → Search          (job-link-alt)
 *   4. degraded primary + alt|source        → Alt link        (job-link-alt)
 *   5. otherwise                            → no link (fallback actions render)
 */
export function resolveJobLink(match: {
  apply_url?: string;
  source_url?: string;
  alt_link?: string;
  verification_status?: VerificationStatus;
}): ResolvedJobLink {
  const vStatus = match.verification_status;
  const applyUrl = cleanUrl(match.apply_url);
  const sourceUrl = (() => {
    const u = cleanUrl(match.source_url);
    return isGoogleIntermediary(u) ? "" : u;
  })();
  const altUrl = (() => {
    const u = cleanUrl(match.alt_link);
    return isGoogleIntermediary(u) ? "" : u;
  })();

  // A degraded/untrusted primary must never be surfaced as a verified apply
  // link (BUG-03). apply_url = direct apply (highest trust); source_url = job
  // listing (medium); alt_link = Google Jobs fallback (lowest, only when the
  // primary is blocked). Neither → "link unavailable" + safe fallback actions.
  const isBadPrimary =
    vStatus === "login_required" ||
    vStatus === "rate_limited" ||
    vStatus === "aggregator_untrusted" ||
    vStatus === "google_intermediary";

  let linkHref = "";
  let linkLabelKey: JobLinkLabelKey = "";
  let linkTestId: JobLinkTestId = "";
  if (applyUrl && !isBadPrimary) {
    linkHref = applyUrl;
    linkLabelKey = "cmdApply";
    linkTestId = "job-link-apply";
  } else if (sourceUrl && !isBadPrimary) {
    linkHref = sourceUrl;
    linkLabelKey = "cmdViewSource";
    linkTestId = "job-link-source";
  } else if (vStatus === "google_intermediary" && altUrl) {
    linkHref = altUrl;
    linkLabelKey = "cmdApplySearch";
    linkTestId = "job-link-alt";
  } else if (isBadPrimary && (altUrl || sourceUrl)) {
    linkHref = altUrl || sourceUrl;
    linkLabelKey = "cmdApplyAlt";
    linkTestId = "job-link-alt";
  }

  // Secondary source link — only when apply and source both exist, differ, and
  // the primary is trusted (never as a substitute for a blocked primary).
  const showSource = !!sourceUrl && sourceUrl !== linkHref && !isBadPrimary && !!applyUrl;

  return { linkHref, linkLabelKey, linkTestId, sourceUrl, altUrl, isBadPrimary, showSource };
}

export type JobFallbackKind = "link" | "copy" | "save";

export interface JobFallbackAction {
  /** Stable identifier — also used as a data-testid suffix and React key. */
  key: "company_website" | "company_site" | "linkedin" | "google" | "copy" | "save";
  kind: JobFallbackKind;
  /** Present for kind === "link": the external search URL to open in a new tab. */
  href?: string;
}

const enc = (s: string) => encodeURIComponent(s.trim());

/**
 * Build the company-site CTA URL.
 *
 * Prefers `employerUrl` when the upstream provider (JSearch) supplies the
 * company's own website — that navigates directly without a search hop. Falls
 * back to a Google search when no employer URL is available. Never returns a
 * URL that was used as an apply link.
 */
export function buildCompanySiteSearchUrl(
  title: string,
  company: string,
  employerUrl?: string,
): string {
  if (employerUrl) return employerUrl;
  const parts = [company, "careers", title].filter(Boolean).join(" ");
  return `https://www.google.com/search?q=${enc(parts)}`;
}

/** LinkedIn jobs search for this role + company. */
export function buildLinkedInSearchUrl(title: string, company: string): string {
  const kw = [title, company].filter(Boolean).join(" ");
  return `https://www.linkedin.com/jobs/search/?keywords=${enc(kw)}`;
}

/** Generic Google search for this job (role + company + "jobs"). */
export function buildGoogleSearchUrl(title: string, company: string): string {
  const parts = [title, company, "jobs"].filter(Boolean).join(" ");
  return `https://www.google.com/search?q=${enc(parts)}`;
}

/** Plain-text payload copied to the clipboard for manual search. */
export function buildCopyText(title: string, company: string): string {
  return [title, company].filter(Boolean).join(" — ");
}

/**
 * Build the ordered list of safe fallback actions for a job card.
 *
 * When `match.employer_url` is present the company-site action uses key
 * "company_website" (label: "Company website") instead of "company_site"
 * (label: "Search company site"), so the UI can show the right label without
 * hinting that the employer URL is a verified apply link.
 *
 * Always returns at least one actionable item as long as the card has a title
 * or company, guaranteeing the card is never a dead-end. "Save to pipeline" is
 * always offered (it needs no URL); "copy" is offered whenever there is text to
 * copy. Search links are added when we have a title or company to search for.
 */
export function getJobFallbackActions(match: {
  title?: string;
  company?: string;
  employer_url?: string;
}): JobFallbackAction[] {
  const title = (match.title || "").trim();
  const company = (match.company || "").trim();
  const employerUrl = (match.employer_url || "").trim();
  const actions: JobFallbackAction[] = [];

  if (title || company) {
    if (employerUrl) {
      actions.push({
        key: "company_website",
        kind: "link",
        href: employerUrl,
      });
    } else {
      actions.push({
        key: "company_site",
        kind: "link",
        href: buildCompanySiteSearchUrl(title, company),
      });
    }
    actions.push({
      key: "linkedin",
      kind: "link",
      href: buildLinkedInSearchUrl(title, company),
    });
    actions.push({
      key: "google",
      kind: "link",
      href: buildGoogleSearchUrl(title, company),
    });
    actions.push({ key: "copy", kind: "copy" });
  }

  // Save to pipeline is always available — it needs no provider URL.
  actions.push({ key: "save", kind: "save" });

  return actions;
}
