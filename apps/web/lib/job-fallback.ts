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
 */

export type JobFallbackKind = "link" | "copy" | "save";

export interface JobFallbackAction {
  /** Stable identifier — also used as a data-testid suffix and React key. */
  key: "company_site" | "linkedin" | "google" | "copy" | "save";
  kind: JobFallbackKind;
  /** Present for kind === "link": the external search URL to open in a new tab. */
  href?: string;
}

const enc = (s: string) => encodeURIComponent(s.trim());

/** Google web search for the company's own careers page for this role. */
export function buildCompanySiteSearchUrl(title: string, company: string): string {
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
 * Always returns at least one actionable item as long as the card has a title
 * or company, guaranteeing the card is never a dead-end. "Save to pipeline" is
 * always offered (it needs no URL); "copy" is offered whenever there is text to
 * copy. Search links are added when we have a title or company to search for.
 */
export function getJobFallbackActions(match: {
  title?: string;
  company?: string;
}): JobFallbackAction[] {
  const title = (match.title || "").trim();
  const company = (match.company || "").trim();
  const actions: JobFallbackAction[] = [];

  if (title || company) {
    actions.push({
      key: "company_site",
      kind: "link",
      href: buildCompanySiteSearchUrl(title, company),
    });
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
