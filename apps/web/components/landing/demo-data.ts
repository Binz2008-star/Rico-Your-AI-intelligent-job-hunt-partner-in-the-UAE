/**
 * demo-data.ts
 *
 * Sealed, static payload used by HeroSection to render the demo conversation.
 * Zero network calls. No fake testimonials, no live counters, no logos.
 * Every role card is clearly labeled "Sample output" in the UI.
 */

export interface DemoTag {
  label: string;
}

export interface DemoRole {
  title: string;
  location: string;
  employmentType: string;
  fitScore: number;
  tags: DemoTag[];
  reasons: string[];
}

export interface DemoTurn {
  role: "user" | "rico";
  text: string;
  card?: DemoRole;
}

export const DEMO_TURNS: DemoTurn[] = [
  {
    role: "user",
    text: "Show me UAE roles that fit my environmental compliance background.",
  },
  {
    role: "rico",
    text:
      "I found a strong match cluster around environmental compliance, HSE-adjacent operations, and reporting roles in Abu Dhabi and Dubai.",
    card: {
      title: "Environmental Compliance Officer",
      location: "Abu Dhabi · Full-time",
      employmentType: "Full-time",
      fitScore: 94,
      tags: [
        { label: "Regulatory reporting" },
        { label: "Audit readiness" },
        { label: "Stakeholder coordination" },
      ],
      reasons: [
        "CV shows direct compliance ownership, not only support work.",
        "Reporting background maps to environmental documentation requirements.",
        "Cross-team execution signals align with UAE employer expectations.",
      ],
    },
  },
];

export const DEMO_PROMPTS: string[] = [
  "Show me UAE roles that fit my environmental compliance background.",
  "Why does this role fit me? What is missing from my CV?",
  "Rewrite my CV summary for UAE employers in English and Arabic.",
  "Find operations roles in Dubai that match my current profile.",
];

export const DEMO_PIPELINE_ROWS = [
  { title: "Compliance Manager", company: "Bank · Dubai", status: "Applied" },
  { title: "Financial Analyst", company: "Consulting · Abu Dhabi", status: "Interview" },
  { title: "Operations Coordinator", company: "Logistics · Sharjah", status: "High fit" },
] as const;

export const DEMO_METRICS = [
  { label: "Saved", value: "12" },
  { label: "Applied", value: "4" },
  { label: "Interviews", value: "2" },
] as const;
