// Mock responses for the Agentic UX demo.
// Replace with real backend calls in Phase 3.

import type { AgenticAnswer } from "./types";

export const SUGGESTED_PROMPTS = [
  "Find UAE jobs that match my CV",
  "What's the best next step in my career?",
  "Review my profile for gaps",
  "Show my application statuses",
  "Help me prepare for an interview",
  "Analyze my skills vs. market demand",
];

function id() {
  return Math.random().toString(36).slice(2, 10);
}

export function getMockAnswer(question: string): Promise<AgenticAnswer> {
  const q = question.toLowerCase();

  let answer: AgenticAnswer;

  if (q.includes("job") || q.includes("find") || q.includes("match")) {
    answer = {
      id: id(),
      type: "job_recommendation",
      title: "Found 3 matches for your profile",
      summary:
        "I found 3 HSE and sustainability roles in the UAE that closely match your background and experience level.",
      reasoning:
        "Your CV highlights 8 years of HSE experience, ISO 45001 certification, and leadership roles — exactly what these employers are seeking.",
      risk_class: "safe",
      reversible: true,
      external_systems: [],
      items: [
        {
          kind: "job",
          data: {
            id: id(),
            title: "Senior HSE Manager",
            company: "ADNOC Group",
            location: "Abu Dhabi, UAE",
            salary: "AED 28,000–32,000/mo",
            match_pct: 94,
            posted_ago: "2 days ago",
            match_reason:
              "Your ISO 45001 cert + 8yr HSE background matches 6/7 core requirements.",
          },
        },
        {
          kind: "job",
          data: {
            id: id(),
            title: "EHS Lead — Construction",
            company: "Emaar Properties",
            location: "Dubai, UAE",
            salary: "AED 22,000–26,000/mo",
            match_pct: 87,
            posted_ago: "4 days ago",
            match_reason:
              "Construction HSE experience aligns well; you may need to highlight your site management background.",
          },
        },
        {
          kind: "job",
          data: {
            id: id(),
            title: "Sustainability Manager",
            company: "Masdar",
            location: "Abu Dhabi, UAE",
            salary: "AED 25,000–30,000/mo",
            match_pct: 82,
            posted_ago: "1 week ago",
            match_reason:
              "Your sustainability background is a strong fit; renewable energy sector is a lateral move worth considering.",
          },
        },
      ],
      actions: [
        {
          id: id(),
          label: "Prepare application",
          icon: "edit_note",
          kind: "approve",
          risk_class: "low",
          requires_approval: true,
          idempotency_key: "prepare-app-" + id(),
        },
        {
          id: id(),
          label: "Save for later",
          icon: "bookmark",
          kind: "approve",
          risk_class: "safe",
          requires_approval: false,
          idempotency_key: "save-job-" + id(),
        },
        {
          id: id(),
          label: "Explain match",
          icon: "lightbulb",
          kind: "chat_continue",
          risk_class: "safe",
          requires_approval: false,
          idempotency_key: "explain-" + id(),
          payload: { message: "Explain why the Senior HSE Manager role at ADNOC is a strong match for me." },
        },
        {
          id: id(),
          label: "Skip",
          icon: "close",
          kind: "dismiss",
          risk_class: "safe",
          requires_approval: false,
          idempotency_key: "skip-" + id(),
        },
      ],
      created_at: new Date(),
      correlation_id: id(),
    };
  } else if (q.includes("profile") || q.includes("gap") || q.includes("cv")) {
    answer = {
      id: id(),
      type: "profile_analysis",
      title: "Your profile has 3 improvement areas",
      summary:
        "Your profile is 72% complete. Three targeted updates would significantly increase recruiter visibility.",
      reasoning:
        "Profiles with specific achievements, LinkedIn URLs, and UAE-specific role keywords receive 3× more recruiter responses in the UAE market.",
      risk_class: "safe",
      reversible: true,
      external_systems: [],
      items: [
        {
          kind: "gap",
          data: {
            id: id(),
            field: "Achievements",
            current: "Not specified",
            suggested: "Add 2–3 measurable outcomes (e.g. 'Reduced incident rate by 40%')",
          },
        },
        {
          kind: "gap",
          data: {
            id: id(),
            field: "LinkedIn URL",
            current: "Missing",
            suggested: "Add your LinkedIn profile URL — 68% of UAE recruiters verify it",
          },
        },
        {
          kind: "gap",
          data: {
            id: id(),
            field: "ISO 45001 renewal date",
            current: "ISO 45001:2018 certified (2019)",
            suggested: "Add renewal year to show currency: 'renewed 2025'",
          },
        },
      ],
      actions: [
        {
          id: id(),
          label: "Fix top gap",
          icon: "auto_fix_high",
          kind: "approve",
          risk_class: "medium",
          requires_approval: true,
          idempotency_key: "fix-gap-" + id(),
        },
        {
          id: id(),
          label: "See all gaps",
          icon: "checklist",
          kind: "navigate",
          risk_class: "safe",
          requires_approval: false,
          idempotency_key: "view-gaps-" + id(),
          payload: { href: "/profile" },
        },
        {
          id: id(),
          label: "Ask how",
          icon: "help_outline",
          kind: "chat_continue",
          risk_class: "safe",
          requires_approval: false,
          idempotency_key: "ask-how-" + id(),
          payload: { message: "How do I write strong HSE achievement bullet points?" },
        },
      ],
      created_at: new Date(),
      correlation_id: id(),
    };
  } else {
    answer = {
      id: id(),
      type: "career_advice",
      title: "Career move analysis",
      summary:
        "Based on your 8 years in HSE, you're well-positioned for either a lateral move into sustainability or a vertical move into regional leadership.",
      reasoning:
        "UAE market demand for ESG-aligned HSE leaders has grown 34% YoY. Your tenure and certifications make you competitive for roles 1–2 levels above your current one.",
      risk_class: "safe",
      reversible: true,
      external_systems: [],
      items: [
        {
          kind: "advice",
          data: {
            id: id(),
            headline: "Vertical: HSE Director",
            detail:
              "You have the experience. The main gap is P&L responsibility — consider asking for budget ownership in your next role.",
            icon: "trending_up",
          },
        },
        {
          kind: "advice",
          data: {
            id: id(),
            headline: "Lateral: Sustainability Manager",
            detail:
              "The ESG transition is the fastest-growing adjacent field. Your ISO 45001 base is directly transferable.",
            icon: "eco",
          },
        },
        {
          kind: "advice",
          data: {
            id: id(),
            headline: "Leverage: UAE Nationalisation",
            detail:
              "Emiratisation targets mean senior HSE roles at ADNOC, DP World, and Masdar are actively being created for senior professionals.",
            icon: "flag",
          },
        },
      ],
      actions: [
        {
          id: id(),
          label: "Find matching roles",
          icon: "search",
          kind: "chat_continue",
          risk_class: "safe",
          requires_approval: false,
          idempotency_key: "find-roles-" + id(),
          payload: { message: "Find UAE HSE Director and Sustainability Manager roles that match my background." },
        },
        {
          id: id(),
          label: "Update profile",
          icon: "edit",
          kind: "navigate",
          risk_class: "safe",
          requires_approval: false,
          idempotency_key: "update-profile-" + id(),
          payload: { href: "/profile" },
        },
      ],
      created_at: new Date(),
      correlation_id: id(),
    };
  }

  return new Promise((resolve) => setTimeout(() => resolve(answer), 1800 + Math.random() * 600));
}
