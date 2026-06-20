// Shared types for the Agentic Conversational UX layer.
// These are UI-layer types only — no backend coupling yet.

export type RiskClass = "safe" | "low" | "medium" | "high" | "critical";
export type PermissionLevel = "read" | "write" | "external" | "irreversible";

export type AgentStatus =
  | "idle"
  | "thinking"
  | "responding"
  | "acting"
  | "waiting"
  | "error";

export type AnswerType =
  | "job_recommendation"
  | "career_advice"
  | "profile_analysis"
  | "application_status"
  | "action_complete"
  | "approval_required";

export type ActionKind =
  | "chat_continue"
  | "navigate"
  | "approve"
  | "dismiss";

export interface ContextualAction {
  id: string;
  label: string;
  icon: string;
  kind: ActionKind;
  risk_class: RiskClass;
  requires_approval: boolean;
  idempotency_key: string;
  payload?: Record<string, unknown>;
}

export interface JobItem {
  id: string;
  title: string;
  company: string;
  location: string;
  salary?: string;
  match_pct: number;
  posted_ago: string;
  match_reason: string;
}

export interface AdvicePoint {
  id: string;
  headline: string;
  detail: string;
  icon: string;
}

export interface ProfileGap {
  id: string;
  field: string;
  current?: string;
  suggested: string;
}

export type AnswerItem =
  | { kind: "job"; data: JobItem }
  | { kind: "advice"; data: AdvicePoint }
  | { kind: "gap"; data: ProfileGap };

export interface AgenticAnswer {
  id: string;
  type: AnswerType;
  title: string;
  summary: string;
  reasoning: string;
  risk_class: RiskClass;
  reversible: boolean;
  external_systems: string[];
  items: AnswerItem[];
  actions: ContextualAction[];
  created_at: Date;
  correlation_id: string;
}

export interface ApprovalState {
  action: ContextualAction;
  answer: AgenticAnswer;
  expiresAt: Date;
}
