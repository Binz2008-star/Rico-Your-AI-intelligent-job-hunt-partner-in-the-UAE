/**
 * Shared Rico API schemas.
 * These drive TypeScript inference across the app and runtime validation
 * where client callers parse responses at the boundary.
 */

import { z } from 'zod';

// ============================================================================
// Auth Schemas
// ============================================================================

export const LoginRequestSchema = z.object({
    email: z.string().email().min(1).max(256),
    password: z.string().min(1).max(128),
    public_user_id_to_merge: z.string().optional(),
});

export const RegisterRequestSchema = z.object({
    email: z.string().min(3).max(256),
    password: z.string().min(8).max(128),
    role: z.enum(['admin', 'user']).default('user'),
    public_user_id_to_merge: z.string().optional(),
});

export const LoginResponseSchema = z.object({
    message: z.string(),
    email: z.string(),
});

export const RegisterResponseSchema = z.object({
    email: z.string(),
    role: z.string(),
    created: z.boolean(),
    email_verification_required: z.boolean().optional(),
});

// ============================================================================
// Job Schemas
// ============================================================================

export const JobActionRequestSchema = z.object({
    job: z.record(z.string(), z.any()),
});

export const JobActionResponseSchema = z.object({
    status: z.string(),
    message: z.string(),
    job_id: z.string().optional(),
});

export const JobListResponseSchema = z.object({
    jobs: z.array(z.record(z.string(), z.any())),
    total: z.number(),
    page: z.number(),
    limit: z.number(),
    pages: z.number(),
});

// ============================================================================
// Application Schemas
// ============================================================================

export const ApplicationCreateRequestSchema = z.object({
    job_id: z.string().min(1),
    title: z.string().min(1),
    company: z.string().min(1),
    location: z.string().default(''),
    url: z.string().default(''),
    status: z.string().default('opened'),
    source: z.string().default('manual'),
});

export const ManualApplicationCreateRequestSchema = z.object({
    title: z.string().min(1),
    company: z.string().min(1),
    location: z.string().default(''),
    url: z.string().default(''),
    status: z.string().default('applied'),
});

export const StatusUpdateRequestSchema = z.object({
    status: z.string().min(1),
    notes: z.string().optional(),
});

export const StatusUpdateResponseSchema = z.object({
    status: z.string(),
    job_id: z.string(),
    message: z.string(),
});

export const ApplicationListResponseSchema = z.object({
    applications: z.array(z.record(z.string(), z.any())),
    total: z.number(),
    page: z.number(),
    limit: z.number(),
    pages: z.number(),
});

// ============================================================================
// Pipeline Schemas
// ============================================================================

export const PipelineStatusResponseSchema = z.object({
    status: z.string(),
    started_at: z.string().optional(),
    finished_at: z.string().optional(),
    jobs_found: z.number().default(0),
    error: z.string().optional(),
    run_id: z.number().optional(),
});

export const PipelineTriggerResponseSchema = z.object({
    status: z.string(),
    message: z.string(),
});

// ============================================================================
// Stats Schemas
// ============================================================================

export const StatsResponseSchema = z.object({
    total_applied: z.number(),
    status_breakdown: z.record(z.string(), z.number()),
    interviews_scheduled: z.number(),
    rejections: z.number(),
    pending: z.number(),
    success_rate: z.number(),
});

// ============================================================================
// Settings Schemas
// ============================================================================

const MatchingGuardrailWarningSchema = z.object({
    code: z.string(),
    field: z.string(),
    severity: z.string().optional(),
    message: z.string(),
    suggestion: z.string().optional(),
    message_ar: z.string().optional(),
    suggestion_ar: z.string().optional(),
}).passthrough();

export const SettingsResponseSchema = z.object({
    include_keywords: z.array(z.string()),
    exclude_keywords: z.array(z.string()),
    min_score: z.number(),
    max_daily_applies: z.number(),
    telegram_chat_id: z.string(),
    score_threshold_apply: z.number(),
    score_threshold_watch: z.number(),
    warnings: z.array(MatchingGuardrailWarningSchema).optional().default([]),
}).passthrough();

export const SettingsUpdateRequestSchema = z.object({
    include_keywords: z.array(z.string()).optional(),
    exclude_keywords: z.array(z.string()).optional(),
    min_score: z.number().optional(),
    max_daily_applies: z.number().optional(),
    telegram_chat_id: z.string().optional(),
    score_threshold_apply: z.number().optional(),
    score_threshold_watch: z.number().optional(),
});

// ============================================================================
// Agent Schemas
// ============================================================================

export const AgentUITypeSchema = z.enum([
    'job_list',
    'job_detail',
    'application_list',
    'stats',
    'pipeline_status',
    'text',
    'confirm',
    'error',
]);

export const ActionStyleSchema = z.enum(['primary', 'secondary', 'danger']);

export const AgentActionSchema = z.object({
    action_id: z.string().default(() => Math.random().toString(36).substring(2, 10)),
    type: z.string(),
    label: z.string(),
    style: ActionStyleSchema.default('secondary'),
    job_id: z.string().optional(),
    job: z.record(z.string(), z.any()).optional(),
    metadata: z.record(z.string(), z.any()).default({}),
});

export const AgentUIComponentSchema = z.object({
    type: AgentUITypeSchema,
    title: z.string().optional(),
    data: z.record(z.string(), z.any()).default({}),
});

export const AgentChatRequestSchema = z.object({
    message: z.string().min(1).max(1000),
    action: AgentActionSchema.optional(),
});

export const AgentUIResponseSchema = z.object({
    message: z.string(),
    ui: AgentUIComponentSchema.optional(),
    actions: z.array(AgentActionSchema).default(() => []),
    tool_used: z.string().optional(),
    execution_time_ms: z.number().default(0),
    success: z.boolean().default(true),
});

// ============================================================================
// Permission Engine Schemas (CAREER-OS-03)
// Must mirror EXECUTE_ALLOWED_ACTIONS in src/schemas/actions.py.
// ============================================================================

// Actions the permission engine is allowed to execute on the user's behalf.
// trigger_pipeline is intentionally absent — it is an admin/scheduler action.
export const EXECUTE_ALLOWED_ACTIONS = [
    "apply", "save", "skip", "not_relevant", "block", "draft", "why", "remind",
] as const;

export type ExecuteAllowedAction = (typeof EXECUTE_ALLOWED_ACTIONS)[number];

export const ExecutePermissionActionRequestSchema = z.object({
    permission_id: z.string().min(1).max(128),
    action: z.enum(EXECUTE_ALLOWED_ACTIONS),
    job_key: z.string().max(256).default(""),
    job: z.record(z.string(), z.unknown()).nullable().optional(),
    source: z.string().max(64).default("permission_card"),
});

export const ExecutePermissionActionResponseSchema = z.object({
    ok: z.boolean(),
    message: z.string(),
    action: z.string(),
    job_key: z.string(),
    source: z.string(),
    user_id: z.string(),
    dry_run: z.boolean(),
    data: z.record(z.string(), z.unknown()).default({}),
    error: z.string().nullable(),
    confidence: z.number(),
    explanation: z.string(),
    duration_ms: z.number().int(),
}).passthrough();

// Use z.input<> so callers may omit fields with .default() (job_key, source).
export type ExecutePermissionActionRequest = z.input<typeof ExecutePermissionActionRequestSchema>;
export type ExecutePermissionActionResponse = z.infer<typeof ExecutePermissionActionResponseSchema>;

// ============================================================================
// Agentic UI Schemas (CAREER-OS-01)
// ============================================================================

export const RicoActionKindSchema = z.enum([
    'navigate',
    'submit',
    'chat_continue',
    'open_drawer',
    'approve',
    'cancel',
]);

export const RicoActionImpactSchema = z.enum(['low', 'medium', 'high']);

export const RicoChatActionSchema = z.object({
    id: z.string(),
    label: z.string(),
    kind: RicoActionKindSchema,
    impact: RicoActionImpactSchema.default('low'),
    requires_confirmation: z.boolean().default(false),
    endpoint: z.string().nullable().optional(),
    href: z.string().nullable().optional(),
    payload: z.record(z.string(), z.unknown()).default({}),
    tracking_key: z.string().nullable().optional(),
});

export const RicoPermissionRequestSchema = z.object({
    id: z.string(),
    title: z.string(),
    summary: z.string(),
    risk_level: z.enum(['medium', 'high']),
    data_used: z.array(z.string()).default([]),
    effects: z.array(z.string()).default([]),
    approve_action: RicoChatActionSchema,
    review_action: RicoChatActionSchema.nullable().optional(),
    cancel_action: RicoChatActionSchema,
});

export const RicoProgressStepSchema = z.object({
    id: z.string(),
    label: z.string(),
    status: z.enum(['pending', 'running', 'complete', 'failed']),
});

export const RicoProposedChangeSchema = z.object({
    field: z.string(),
    current_value: z.unknown().nullable().optional(),
    proposed_value: z.unknown(),
    source: z.enum(['chat', 'cv', 'file', 'screenshot', 'system', 'user_action']),
});

export const RicoAttachmentPurposeSchema = z.enum([
    'cv_resume',
    'job_post',
    'recruiter_message',
    'application_form',
    'certificate',
    'offer_letter',
    'contract_or_legalish',
    'company_profile',
    'public_comment',
    'application_evidence',
    'unknown_document',
]);

export const RicoAttachmentAnalysisSchema = z.object({
    id: z.string(),
    filename: z.string().nullable().optional(),
    mime_type: z.string().nullable().optional(),
    purpose: RicoAttachmentPurposeSchema,
    confidence: z.number(),
    extracted_summary: z.string().nullable().optional(),
    extracted_fields: z.record(z.string(), z.unknown()).default({}),
    warnings: z.array(z.string()).default([]),
});

export const RicoAgenticUiSchema = z.object({
    actions: z.array(RicoChatActionSchema).default([]),
    permission_request: RicoPermissionRequestSchema.nullable().optional(),
    progress: z.array(RicoProgressStepSchema).default([]),
    proposed_changes: z.array(RicoProposedChangeSchema).default([]),
    attachment_analysis: z.array(RicoAttachmentAnalysisSchema).default([]),
});

// ============================================================================
// Rico Chat Schemas
// ============================================================================

export const RicoChatRequestSchema = z.object({
    message: z.string().max(4096),
});

export const RicoPublicChatRequestSchema = z.object({
    message: z.string().max(2048),
    session_id: z.string().min(8).max(64).optional(),
    email: z.string().email().optional(),
});

export const RicoFeedbackRequestSchema = z.object({
    job_id: z.string().min(1).max(100),
    feedback_type: z.enum(['positive', 'negative', 'neutral']),
    rating: z.number().int().min(1).max(5),
    comment: z.string().max(500).optional(),
});

const StringFromUnknownSchema = z.preprocess((value) => {
    if (value === null || value === undefined) return undefined;
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    return value;
}, z.string().optional());

const StringArrayFromUnknownSchema = z.preprocess((value) => {
    if (value === null || value === undefined) return undefined;
    if (!Array.isArray(value)) return value;
    return value
        .filter((item) => typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean')
        .map((item) => typeof item === 'string' ? item : String(item));
}, z.array(z.string()).optional());

export const MeResponseSchema = z.object({
    email: z.string().nullable(),
    role: z.string(),
    authenticated: z.boolean(),
    guest: z.boolean().optional(),
    name: z.string().nullable().optional(),
    // Server-computed owner flag (immutable users.id vs RICO_OWNER_USER_ID).
    // The owner id itself is never sent to the browser — only this boolean.
    is_owner: z.boolean().optional(),
});

// GET /api/v1/onboarding/status — the canonical onboarding-completion signal.
// `complete` is the only value the UI routes on; `status`/`source`/`missing_fields`
// are informational. `profile_exists` is informational ONLY and must never be
// treated as completion (the backend gate + persisted state decide `complete`).
export const OnboardingStatusResponseSchema = z.object({
    status: z.enum(['pending', 'in_progress', 'completed']),
    complete: z.boolean(),
    source: z.enum(['persisted', 'derived_legacy']),
    missing_fields: z.array(z.string()),
    profile_exists: z.boolean(),
    profile_completeness: z.number(),
});

// verification_status contract — mirrors the backend's CURRENT emit
// vocabulary (2026-07-19 production incident: the old 2-value enum rejected
// "aggregator_untrusted" and discarded an entire valid chat response on the
// REST fallback path — validateShape threw, the user saw a generic error).
// Sources of truth on the backend:
//   * src/services/source_quality.py — live_verified / login_required /
//     rate_limited / aggregator_untrusted / needs_source_verification
//   * src/services/job_link.py — google_intermediary / expired
//   * legacy chat pipeline defaults — live / lead_needs_verification
export const KNOWN_VERIFICATION_STATUSES = [
    'live_verified',
    'login_required',
    'rate_limited',
    'aggregator_untrusted',
    'needs_source_verification',
    'google_intermediary',
    'expired',
    'live',
    'lead_needs_verification',
] as const;

// Forward compatibility, fail-SAFE: an unknown future status must never
// discard the response wholesale — and must never be promoted to a trusted
// value. It normalizes to 'needs_source_verification' (the cautious
// presentation) with a console warning so drift stays visible.
const VerificationStatusSchema = z.preprocess((value) => {
    if (value == null || value === '') return undefined;
    if (typeof value !== 'string') return undefined;
    if ((KNOWN_VERIFICATION_STATUSES as readonly string[]).includes(value)) return value;
    console.warn(
        `Unknown verification_status "${value}" — normalized to needs_source_verification`,
    );
    return 'needs_source_verification';
}, z.enum(KNOWN_VERIFICATION_STATUSES).optional());

/* ── Complementary fail-open hardening (on top of the #1191 contract) ─────
   #1191 fixed verification_status; the SAME failure class remained open for
   every other annotation field: a null confidence, a numeric-string score,
   a null top-level boolean/record, or any one malformed match row would
   still reject the ENTIRE reply at validateShape and show the generic FAIL
   bubble. Annotation-grade fields may degrade — never reject a reply. */

/** Tolerant number: numeric strings coerce; anything else → undefined. */
const TolerantScoreSchema = z.preprocess((value) => {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
        return Number(value);
    }
    return undefined;
}, z.number().optional());

/** Tolerant confidence: known tiers pass; anything else (null, new tiers) → undefined. */
const TolerantConfidenceSchema = z.preprocess(
    (value) => (value === 'high' || value === 'medium' || value === 'low' ? value : undefined),
    z.enum(['high', 'medium', 'low']).optional(),
);

export const JobMatchSchema = z.object({
    title: StringFromUnknownSchema.default('Untitled role'),
    company: StringFromUnknownSchema.default('Unknown company'),
    location: StringFromUnknownSchema,
    score: TolerantScoreSchema,
    why: StringFromUnknownSchema,
    actions: StringArrayFromUnknownSchema,
    confidence: TolerantConfidenceSchema,
    match_reasons: StringArrayFromUnknownSchema,
    match_concerns: StringArrayFromUnknownSchema,
    missing_facts: StringArrayFromUnknownSchema,
    recommended_action: StringFromUnknownSchema,
    // Job authenticity fields — optional so existing responses without them still parse.
    apply_url: StringFromUnknownSchema,
    source_url: StringFromUnknownSchema,
    verification_status: VerificationStatusSchema,
    // Source provenance from backend dedup — optional so responses without them
    // still parse. Tolerant: a malformed value is dropped, never a parse error.
    sources: StringArrayFromUnknownSchema.optional(),
    duplicate_count: z.coerce.number().int().positive().optional().catch(undefined),
}).passthrough();

export const RicoOptionSchema = z.object({
    action: StringFromUnknownSchema.default('send_message'),
    label: StringFromUnknownSchema.default('Continue'),
    message: StringFromUnknownSchema,
    role: StringFromUnknownSchema,
}).passthrough();

export const NextActionSchema = z.object({
    action: StringFromUnknownSchema.default('send_message'),
    label: StringFromUnknownSchema.default('Continue'),
    message: StringFromUnknownSchema,
    role: StringFromUnknownSchema,
}).passthrough();

export const RicoChatResponseSchema = z.object({
    response: StringFromUnknownSchema,
    reply: StringFromUnknownSchema,
    message: StringFromUnknownSchema,
    content: StringFromUnknownSchema,
    answer: StringFromUnknownSchema,
    text: StringFromUnknownSchema,
    data: z.object({
        response: StringFromUnknownSchema,
        reply: StringFromUnknownSchema,
        message: StringFromUnknownSchema,
        content: StringFromUnknownSchema,
        text: StringFromUnknownSchema,
    }).passthrough().optional(),
    type: StringFromUnknownSchema,
    // Per-row salvage (batch-row-isolation, same philosophy as backend #887):
    // one malformed match is DROPPED with a console warning — it can never
    // reject the whole reply into the generic FAIL bubble.
    matches: z
        .array(z.unknown())
        .nullable()
        .optional()
        .transform((value) => {
            if (!value) return undefined;
            const rows: Array<z.infer<typeof JobMatchSchema>> = [];
            for (const item of value) {
                const parsed = JobMatchSchema.safeParse(item);
                if (parsed.success) rows.push(parsed.data);
                else console.warn('Dropped malformed job match from chat response', parsed.error.flatten());
            }
            return rows;
        }),
    options: z.array(RicoOptionSchema).nullable().optional().transform((value) => value ?? undefined),
    next_action: StringFromUnknownSchema,
    response_source: StringFromUnknownSchema,
    role: StringFromUnknownSchema,
    reasons: StringArrayFromUnknownSchema,
    next_actions: z.array(NextActionSchema).nullable().optional().transform((value) => value ?? undefined),
    success: z.boolean().nullable().optional().transform((v) => v ?? undefined),
    debug_id: StringFromUnknownSchema,
    error: StringFromUnknownSchema,
    error_ref: StringFromUnknownSchema,
    provider: StringFromUnknownSchema,
    model: StringFromUnknownSchema,
    profile_context_present: z.boolean().nullable().optional().transform((v) => v ?? undefined),
    intent: StringFromUnknownSchema,
    entities: z.record(z.string(), z.unknown()).nullable().optional().transform((v) => v ?? undefined),
    tool_args: z.record(z.string(), z.unknown()).nullable().optional().transform((v) => v ?? undefined),
    field_status: StringFromUnknownSchema,
    updated: z.record(z.string(), z.unknown()).optional(),
    profile: z.record(z.string(), z.unknown()).optional(),
    target_roles: StringArrayFromUnknownSchema,
    openai_available: z.boolean().optional(),
    deepseek_available: z.boolean().optional(),
    hf_available: z.boolean().optional(),
    provider_available: z.boolean().optional(),
    openai_model: StringFromUnknownSchema,
    jotform_form_id: StringFromUnknownSchema.nullable(),
    // Tolerant like every other field here: older backends (and any cached
    // reply) send agentic_ui: null for card-less text replies — that null
    // must normalize to "absent", never reject the whole reply into the
    // generic FAIL bubble (2026-07-19 profile-report incident). The new
    // backend omits the key entirely; a real object passes through unchanged.
    agentic_ui: RicoAgenticUiSchema
        .nullable()
        .optional()
        .transform((value) => value ?? undefined),
}).passthrough();

export const RicoProfileResponseSchema = z.object({
    profile_exists: z.boolean(),
    email: z.string().nullable().optional(),
    user_id: z.string().nullable().optional(),
    name: z.string().nullable().optional(),
    phone: z.string().nullable().optional(),
    telegram_username: z.string().nullable().optional(),
    target_roles: z.array(z.string()).nullish(),
    preferred_cities: z.array(z.string()).nullish(),
    salary_expectation_aed: z.number().nullable().optional(),
    minimum_salary_aed: z.number().nullable().optional(),
    skills: z.array(z.string()).nullish(),
    industries: z.array(z.string()).nullish(),
    visa_status: z.string().nullable().optional(),
    notice_period: z.string().nullable().optional(),
    years_experience: z.number().nullable().optional(),
    current_role: z.string().nullable().optional(),
    current_company: z.string().nullable().optional(),
    linkedin_url: z.string().nullable().optional(),
    completeness_score: z.number().nullable().optional(),
    settings: z.record(z.string(), z.unknown()).optional(),
    warnings: z.array(MatchingGuardrailWarningSchema).optional().default([]),
}).passthrough();

export const SavedSearchSchema = z.object({
    id: z.union([z.string(), z.number()]).transform(String),
    query: z.string(),
    filters: z.record(z.string(), z.unknown()),
    created_at: z.string(),
}).passthrough();

export const SavedSearchesResponseSchema = z.object({
    searches: z.array(SavedSearchSchema),
    total: z.number(),
});

// #1249 — scheduled saved searches (schedule metadata lives in filters.schedule
// on the backend; the status endpoint surfaces it as a first-class object).
export const ScheduledSearchResultSchema = z.object({
    title: z.string(),
    company: z.string(),
    location: z.string().optional().default(""),
    score: z.number().optional().default(0),
    link: z.string(),
    salary_known: z.boolean().optional().default(false),
    salary_aed: z.number().nullable().optional(),
    why: z.string().optional().default(""),
}).passthrough();

export const ScheduledSearchScheduleSchema = z.object({
    enabled: z.boolean(),
    cadence: z.string().optional().default("daily"),
    city: z.string().nullable().optional(),
    min_salary_aed: z.number().nullable().optional(),
    last_run_at: z.string().nullable().optional(),
    last_run_new: z.number().optional().default(0),
    last_results: z.array(ScheduledSearchResultSchema).optional().default([]),
}).passthrough();

export const ScheduledSearchSchema = z.object({
    id: z.string().nullable(),
    query: z.string().nullable().optional(),
    schedule: ScheduledSearchScheduleSchema,
}).passthrough();

export const ScheduledSearchesResponseSchema = z.object({
    schedules: z.array(ScheduledSearchSchema),
    total: z.number(),
});

export const RicoChatHistoryMessageSchema = z.object({
    role: z.string(),
    content: z.string(),
    timestamp: z.string().nullable().optional(),
}).passthrough();

export const RicoChatHistoryResponseSchema = z.object({
    messages: z.array(RicoChatHistoryMessageSchema),
    total: z.number(),
    has_more: z.boolean(),
}).passthrough();

// Sessions rail (#1193): one entry per chat thread, derived server-side from
// rico_chat_history. id "default" is the legacy thread; others are UUIDs.
export const RicoChatSessionSchema = z.object({
    id: z.string(),
    title: z.string().nullable().optional(),
    message_count: z.number(),
    user_turns: z.number(),
    started_at: z.string().nullable().optional(),
    last_activity: z.string().nullable().optional(),
}).passthrough();

export const RicoChatSessionsResponseSchema = z.object({
    sessions: z.array(RicoChatSessionSchema),
    total: z.number(),
}).passthrough();

export const ParsedCVSchema = z.object({
    text: z.string(),
    emails: z.array(z.string()),
    phones: z.array(z.string()),
    skills: z.array(z.string()),
    certifications: z.array(z.string()),
    languages: z.array(z.string()),
    years_experience_hint: z.number().nullable().optional(),
    years_experience: z.number().nullable().optional(),
    extraction_quality: z.string().optional(),
    extracted_chars: z.number().optional(),
}).passthrough();

export const ProfilePreviewSchema = z.object({
    name: z.string().nullable(),
    email: z.string().nullable(),
    phone: z.string().nullable(),
    current_role: z.string().nullable(),
    experience_years: z.number().nullable(),
    target_roles: z.array(z.string()),
    skills_detected: z.array(z.string()),
    existing_skills: z.array(z.string()),
    skills: z.array(z.string()),
    certifications: z.array(z.string()),
    languages: z.array(z.string()),
}).passthrough();

export const UploadCVResponseSchema = z.object({
    ok: z.boolean(),
    status: z.string(),
    document_type: z.string().optional(),
    extraction_quality: z.string().optional(),
    extracted_chars: z.number().optional(),
    filename: z.string().optional(),
    preview: ProfilePreviewSchema.optional(),
    parsed: ParsedCVSchema.optional(),
    message: z.string().optional(),
    user_id: z.string().optional(),
    upload_id: z.string().nullable().optional(),
}).passthrough();

export const ConfirmCVProfileResponseSchema = z.object({
    ok: z.boolean(),
    status: z.string(),
    message: z.string(),
    profile: z.record(z.string(), z.unknown()),
}).passthrough();

export const ProfileUpdateResponseSchema = z.object({
    status: z.string(),
    updated_fields: z.array(z.string()),
    warnings: z.array(MatchingGuardrailWarningSchema).optional().default([]),
}).passthrough();

// ============================================================================
// Memory Schemas (for persistent memory system)
// ============================================================================

export const LongitudinalMemorySchema = z.object({
    user_id: z.string(),
    timestamp: z.string(),
    event_type: z.enum([
        'job_viewed',
        'job_applied',
        'job_saved',
        'job_skipped',
        'company_blocked',
        'recruiter_contact',
        'interview_scheduled',
        'offer_received',
        'offer_accepted',
        'offer_rejected',
        'compensation_update',
        'preference_update',
    ]),
    job_id: z.string().optional(),
    company: z.string().optional(),
    recruiter: z.string().optional(),
    compensation: z.object({
        salary: z.number().optional(),
        equity: z.string().optional(),
        bonus: z.number().optional(),
        benefits: z.array(z.string()).optional(),
    }).optional(),
    preferences: z.object({
        locations: z.array(z.string()).optional(),
        roles: z.array(z.string()).optional(),
        industries: z.array(z.string()).optional(),
        remote: z.boolean().optional(),
        min_salary: z.number().optional(),
    }).optional(),
    metadata: z.record(z.string(), z.any()).optional(),
});

export const TrajectoryHistorySchema = z.object({
    user_id: z.string(),
    timestamp: z.string(),
    trajectory_state: z.object({
        current_role: z.string(),
        target_roles: z.array(z.string()),
        career_stage: z.enum(['early', 'mid', 'senior', 'executive']),
        momentum_score: z.number(),
        convergence_probability: z.number(),
        strategic_positioning: z.object({
            market_fit: z.number(),
            skill_alignment: z.number(),
            opportunity_density: z.number(),
        }),
    }),
    nodes: z.array(z.object({
        id: z.string(),
        type: z.enum(['opportunity', 'milestone', 'decision', 'outcome']),
        title: z.string(),
        probability: z.number(),
        timing: z.object({
            optimal: z.string().optional(),
            window_start: z.string().optional(),
            window_end: z.string().optional(),
            decay_rate: z.number().optional(),
        }),
    })),
});

export const RecruiterInteractionSchema = z.object({
    user_id: z.string(),
    recruiter_id: z.string(),
    recruiter_name: z.string(),
    company: z.string(),
    timestamp: z.string(),
    interaction_type: z.enum([
        'initial_contact',
        'screening_call',
        'technical_interview',
        'behavioral_interview',
        'offer_negotiation',
        'follow_up',
    ]),
    outcome: z.enum([
        'pending',
        'positive',
        'negative',
        'offer',
        'rejected',
    ]),
    response_time_hours: z.number().optional(),
    communication_style: z.enum(['formal', 'casual', 'direct', 'relationship-focused']).optional(),
    metadata: z.record(z.string(), z.any()).optional(),
});

export const CompensationTargetSchema = z.object({
    user_id: z.string(),
    timestamp: z.string(),
    target: z.object({
        base_salary: z.number(),
        equity: z.string().optional(),
        bonus: z.number().optional(),
        benefits_value: z.number().optional(),
        total_compensation: z.number(),
    }),
    current: z.object({
        base_salary: z.number(),
        equity: z.string().optional(),
        bonus: z.number().optional(),
        benefits_value: z.number().optional(),
        total_compensation: z.number(),
    }),
    trajectory: z.object({
        target_date: z.string(),
        confidence: z.number(),
        required_moves: z.array(z.string()),
    }),
});

export const StrategicPreferenceSchema = z.object({
    user_id: z.string(),
    timestamp: z.string(),
    preferences: z.object({
        career_velocity: z.enum(['conservative', 'moderate', 'aggressive']),
        risk_tolerance: z.enum(['low', 'medium', 'high']),
        geographic_flexibility: z.enum(['none', 'regional', 'national', 'global']),
        industry_focus: z.array(z.string()),
        role_evolution: z.enum(['specialist', 'generalist', 'leader']),
        work_life_balance: z.number().min(0).max(10),
        learning_priority: z.number().min(0).max(10),
        compensation_priority: z.number().min(0).max(10),
        title_progression: z.array(z.string()),
    }),
});

export const OpportunityWeightingSchema = z.object({
    user_id: z.string(),
    opportunity_id: z.string(),
    timestamp: z.string(),
    weights: z.object({
        strategic_fit: z.number().min(0).max(1),
        compensation_alignment: z.number().min(0).max(1),
        growth_potential: z.number().min(0).max(1),
        market_timing: z.number().min(0).max(1),
        recruiter_quality: z.number().min(0).max(1),
        cultural_alignment: z.number().min(0).max(1),
    }),
    momentum_score: z.number(),
    decay_probability: z.number(),
    saturation_window: z.object({
        start: z.string().optional(),
        end: z.string().optional(),
        intensity: z.number().min(0).max(1),
    }),
});

// ============================================================================
// Type Exports
// ============================================================================

export type LoginRequest = z.infer<typeof LoginRequestSchema>;
export type RegisterRequest = z.infer<typeof RegisterRequestSchema>;
export type LoginResponse = z.infer<typeof LoginResponseSchema>;
export type RegisterResponse = z.infer<typeof RegisterResponseSchema>;

export type JobActionRequest = z.infer<typeof JobActionRequestSchema>;
export type JobActionResponse = z.infer<typeof JobActionResponseSchema>;
export type JobListResponse = z.infer<typeof JobListResponseSchema>;

export type ApplicationCreateRequest = z.infer<typeof ApplicationCreateRequestSchema>;
export type ManualApplicationCreateRequest = z.infer<typeof ManualApplicationCreateRequestSchema>;
export type StatusUpdateRequest = z.infer<typeof StatusUpdateRequestSchema>;
export type StatusUpdateResponse = z.infer<typeof StatusUpdateResponseSchema>;
export type ApplicationListResponse = z.infer<typeof ApplicationListResponseSchema>;

export type PipelineStatusResponse = z.infer<typeof PipelineStatusResponseSchema>;
export type PipelineTriggerResponse = z.infer<typeof PipelineTriggerResponseSchema>;

export type StatsResponse = z.infer<typeof StatsResponseSchema>;

export type SettingsResponse = z.infer<typeof SettingsResponseSchema>;
export type SettingsUpdateRequest = z.infer<typeof SettingsUpdateRequestSchema>;

export type AgentAction = z.infer<typeof AgentActionSchema>;
export type AgentUIComponent = z.infer<typeof AgentUIComponentSchema>;
export type AgentChatRequest = z.infer<typeof AgentChatRequestSchema>;
export type AgentUIResponse = z.infer<typeof AgentUIResponseSchema>;

export type RicoActionKind = z.infer<typeof RicoActionKindSchema>;
export type RicoActionImpact = z.infer<typeof RicoActionImpactSchema>;
export type RicoChatAction = z.infer<typeof RicoChatActionSchema>;
export type RicoPermissionRequest = z.infer<typeof RicoPermissionRequestSchema>;
export type RicoProgressStep = z.infer<typeof RicoProgressStepSchema>;
export type RicoProposedChange = z.infer<typeof RicoProposedChangeSchema>;
export type RicoAttachmentPurpose = z.infer<typeof RicoAttachmentPurposeSchema>;
export type RicoAttachmentAnalysis = z.infer<typeof RicoAttachmentAnalysisSchema>;
export type RicoAgenticUi = z.infer<typeof RicoAgenticUiSchema>;

export type RicoChatRequest = z.infer<typeof RicoChatRequestSchema>;
export type RicoPublicChatRequest = z.infer<typeof RicoPublicChatRequestSchema>;
export type RicoFeedbackRequest = z.infer<typeof RicoFeedbackRequestSchema>;
export type MeResponse = z.infer<typeof MeResponseSchema>;
export type OnboardingStatusResponse = z.infer<typeof OnboardingStatusResponseSchema>;
export type JobMatch = z.infer<typeof JobMatchSchema>;
export type RicoChatResponse = z.infer<typeof RicoChatResponseSchema>;
export type RicoProfileResponse = z.infer<typeof RicoProfileResponseSchema>;
export type SavedSearch = z.infer<typeof SavedSearchSchema>;
export type SavedSearchesResponse = z.infer<typeof SavedSearchesResponseSchema>;
export type RicoChatHistoryResponse = z.infer<typeof RicoChatHistoryResponseSchema>;
export type RicoChatSession = z.infer<typeof RicoChatSessionSchema>;
export type RicoChatSessionsResponse = z.infer<typeof RicoChatSessionsResponseSchema>;
export type ParsedCV = z.infer<typeof ParsedCVSchema>;
export type ProfilePreview = z.infer<typeof ProfilePreviewSchema>;
export type UploadCVResponse = z.infer<typeof UploadCVResponseSchema>;
export type ConfirmCVProfileResponse = z.infer<typeof ConfirmCVProfileResponseSchema>;
export type ProfileUpdateResponse = z.infer<typeof ProfileUpdateResponseSchema>;

export type LongitudinalMemory = z.infer<typeof LongitudinalMemorySchema>;
export type TrajectoryHistory = z.infer<typeof TrajectoryHistorySchema>;
export type RecruiterInteraction = z.infer<typeof RecruiterInteractionSchema>;
export type CompensationTarget = z.infer<typeof CompensationTargetSchema>;
export type StrategicPreference = z.infer<typeof StrategicPreferenceSchema>;
export type OpportunityWeighting = z.infer<typeof OpportunityWeightingSchema>;
