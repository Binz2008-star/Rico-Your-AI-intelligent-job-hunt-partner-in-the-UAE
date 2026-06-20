/**
 * Rico Agentic UX — Mock Data
 * 
 * SCOPE: UI proof only. Read-only. No backend calls.
 * DO NOT use this data for any real execution logic.
 */

export type RicoCardType = 'insight' | 'action_proposal' | 'result' | 'receipt' | 'warning';
export type RiskClass = 'safe' | 'moderate' | 'destructive';
export type CardStatus = 'pending' | 'approved' | 'rejected' | 'executed' | 'superseded';
export type ActionVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type RicoStatus = 'idle' | 'thinking' | 'proposing' | 'waiting_approval' | 'executing' | 'done' | 'needs_attention';

export interface RicoAction {
  id: string;
  label: string;
  variant: ActionVariant;
  risk_class: RiskClass;
  requires_approval: boolean;
  target_system?: string;
  expected_effect?: string;
  icon?: string;
}

export interface RicoCard {
  id: string;
  type: RicoCardType;
  title: string;
  body: string;
  reasoning?: string;
  data?: Record<string, unknown>;
  actions: RicoAction[];
  risk_class: RiskClass;
  undo_available: boolean;
  audit_ref?: string;
  created_at: string;
  status: CardStatus;
}

export interface ApprovalRecord {
  action_id: string;
  actor_user_id: string;
  card_id: string;
  approved_at: string;
  risk_class: RiskClass;
  target_system: string;
  expected_effect: string;
  undo_available: boolean;
  idempotency_key: string;
}

export interface PromptChip {
  id: string;
  label: string;
  icon: string;
  query: string;
  context_tag: string;
}

// ---------------------------------------------------------------------------
// MOCK: Suggested prompt chips
// ---------------------------------------------------------------------------
export const MOCK_PROMPT_CHIPS: PromptChip[] = [
  {
    id: 'chip-1',
    label: 'Jobs matching my CV',
    icon: 'briefcase',
    query: 'What jobs in the UAE match my current CV?',
    context_tag: 'discovery',
  },
  {
    id: 'chip-2',
    label: 'Why was I skipped?',
    icon: 'help-circle',
    query: "Why wasn't I shortlisted for the last 3 applications?",
    context_tag: 'analysis',
  },
  {
    id: 'chip-3',
    label: 'Improve my headline',
    icon: 'edit-3',
    query: 'Suggest a stronger LinkedIn headline for my profile.',
    context_tag: 'profile',
  },
  {
    id: 'chip-4',
    label: 'Application pipeline',
    icon: 'bar-chart-2',
    query: 'Show me a summary of my current applications pipeline.',
    context_tag: 'pipeline',
  },
  {
    id: 'chip-5',
    label: 'Next best action',
    icon: 'zap',
    query: "What's the most impactful thing I can do today for my job search?",
    context_tag: 'strategy',
  },
];

// ---------------------------------------------------------------------------
// MOCK: Conversation cards
// ---------------------------------------------------------------------------
export const MOCK_CARDS: RicoCard[] = [
  {
    id: 'card-insight-001',
    type: 'insight',
    title: 'Your CV matches 14 active roles in Dubai & Abu Dhabi',
    body:
      'Based on your current CV and target roles, Rico found 14 open positions with a match score above 78%. The top 3 are in Financial Services, PropTech, and Logistics sectors — all actively hiring for your level.',
    reasoning:
      'Rico cross-referenced your CV keywords, seniority level, and your saved target roles against jobs posted in the last 7 days on LinkedIn UAE, Bayt, and GulfTalent.',
    data: {
      total_matches: 14,
      top_sectors: ['Financial Services', 'PropTech', 'Logistics'],
      avg_match_score: 82,
      date_range: 'Last 7 days',
    },
    actions: [
      {
        id: 'action-view-matches',
        label: 'View all matches',
        variant: 'primary',
        risk_class: 'safe',
        requires_approval: false,
        icon: 'list',
      },
      {
        id: 'action-apply-top',
        label: 'Apply to top 3',
        variant: 'secondary',
        risk_class: 'moderate',
        requires_approval: true,
        target_system: 'applications',
        expected_effect: 'Creates 3 draft applications in your pipeline for your review.',
        icon: 'send',
      },
    ],
    risk_class: 'safe',
    undo_available: false,
    audit_ref: 'audit-mock-001',
    created_at: new Date().toISOString(),
    status: 'pending',
  },
  {
    id: 'card-proposal-001',
    type: 'action_proposal',
    title: 'Rico wants to draft a cover letter for Noon.com — Senior Product Manager',
    body:
      'Rico can generate a tailored cover letter for the Noon.com SPM role, using your work history and the job description. It will be saved as a draft — nothing will be sent without your explicit approval.',
    reasoning:
      'This role has an 91% match score against your CV. The hiring manager typically responds within 48 hours to strong applicants. Personalised cover letters increase shortlist rates by ~34% for this role type.',
    data: {
      company: 'Noon.com',
      role: 'Senior Product Manager',
      match_score: 91,
      location: 'Dubai, UAE',
      posted: '2 days ago',
    },
    actions: [
      {
        id: 'action-draft-cover',
        label: 'Draft cover letter',
        variant: 'primary',
        risk_class: 'safe',
        requires_approval: false,
        target_system: 'document_generator',
        expected_effect: 'Creates a draft cover letter in your Documents section. Nothing is sent.',
        icon: 'file-text',
      },
      {
        id: 'action-skip',
        label: 'Skip for now',
        variant: 'ghost',
        risk_class: 'safe',
        requires_approval: false,
        icon: 'x',
      },
    ],
    risk_class: 'safe',
    undo_available: true,
    audit_ref: 'audit-mock-002',
    created_at: new Date().toISOString(),
    status: 'pending',
  },
  {
    id: 'card-warning-001',
    type: 'warning',
    title: 'Your LinkedIn headline is limiting your discoverability',
    body:
      'Recruiters searching for your profile are using terms like "Product Strategy", "Digital Transformation", and "UAE" — none of which appear in your current headline. This reduces your profile ranking in recruiter searches by an estimated 60%.',
    reasoning:
      'Rico analysed the last 15 LinkedIn recruiter search patterns that resulted in profile views for your level in the UAE market.',
    actions: [
      {
        id: 'action-suggest-headline',
        label: 'Suggest new headline',
        variant: 'primary',
        risk_class: 'safe',
        requires_approval: false,
        icon: 'edit-3',
      },
      {
        id: 'action-dismiss-warning',
        label: 'Dismiss',
        variant: 'ghost',
        risk_class: 'safe',
        requires_approval: false,
        icon: 'x',
      },
    ],
    risk_class: 'safe',
    undo_available: false,
    audit_ref: 'audit-mock-003',
    created_at: new Date().toISOString(),
    status: 'pending',
  },
  {
    id: 'card-receipt-001',
    type: 'receipt',
    title: 'Done — Cover letter drafted for Careem',
    body:
      'Rico created a tailored cover letter for the Careem Head of Growth role and saved it to your Documents. No emails were sent. Review it before you decide to attach it to any application.',
    data: {
      document_title: 'Cover Letter — Careem Head of Growth',
      created_at: new Date().toISOString(),
      word_count: 312,
      status: 'Draft — not sent',
    },
    actions: [
      {
        id: 'action-view-doc',
        label: 'Review document',
        variant: 'primary',
        risk_class: 'safe',
        requires_approval: false,
        icon: 'eye',
      },
    ],
    risk_class: 'safe',
    undo_available: true,
    audit_ref: 'audit-mock-004',
    created_at: new Date().toISOString(),
    status: 'executed',
  },
];

export const MOCK_QUICK_RESPONSES: Record<string, RicoCard[]> = {
  "What jobs in the UAE match my current CV?": [MOCK_CARDS[0]],
  "Why wasn't I shortlisted for the last 3 applications?": [MOCK_CARDS[2]],
  "Suggest a stronger LinkedIn headline for my profile.": [MOCK_CARDS[2]],
  "Show me a summary of my current applications pipeline.": [MOCK_CARDS[0], MOCK_CARDS[3]],
  "What's the most impactful thing I can do today for my job search?": [MOCK_CARDS[1], MOCK_CARDS[2]],
};
