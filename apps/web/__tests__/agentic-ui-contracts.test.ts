/**
 * apps/web/__tests__/agentic-ui-contracts.test.ts
 *
 * CAREER-OS-01: Zod schema tests for optional agentic_ui contracts.
 *
 * Verifies:
 * - Old RicoChatResponse payloads still validate without agentic_ui.
 * - New responses with agentic_ui validate correctly.
 * - Invalid agentic_ui values are rejected by individual schemas.
 */

import { describe, expect, it } from 'vitest';

import {
    RicoChatActionSchema,
    RicoChatResponseSchema,
    RicoAgenticUiSchema,
    RicoAttachmentAnalysisSchema,
    RicoPermissionRequestSchema,
    RicoProgressStepSchema,
    RicoProposedChangeSchema,
} from '@/lib/schemas';

// ── Helpers ───────────────────────────────────────────────────────────────────

const approveAction = {
    id: 'approve',
    label: 'Approve',
    kind: 'approve' as const,
    impact: 'high' as const,
    requires_confirmation: true,
    payload: {},
};

const cancelAction = {
    id: 'cancel',
    label: 'Cancel',
    kind: 'cancel' as const,
    impact: 'low' as const,
    requires_confirmation: false,
    payload: {},
};

// ── Backward compatibility ────────────────────────────────────────────────────

describe('RicoChatResponseSchema — backward compatibility', () => {
    it('accepts minimal text-only response without agentic_ui', () => {
        const result = RicoChatResponseSchema.safeParse({ message: 'Hello!' });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.agentic_ui).toBeUndefined();
        }
    });

    it('accepts full legacy production response shape', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'Welcome to Rico AI. Upload your CV or tell me your target role.',
            type: 'onboarding',
            matches: [],
            options: [],
            next_action: null,
            next_actions: [],
            intent: null,
            response_source: 'keyword',
            provider: null,
            provider_state: null,
            reasons: [],
            role: null,
            success: true,
            error_ref: null,
            trace_id: 'ERR-83D937A1',
            response: null,
            openai_available: true,
            deepseek_available: true,
            hf_available: true,
            provider_available: true,
            openai_model: 'deepseek-v4-flash',
            profile_context_present: false,
            jotform_form_id: '261277622782059',
            debug_id: '361d9f64be81',
        });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.agentic_ui).toBeUndefined();
        }
    });

    it('accepts job search results response without agentic_ui', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'Found 3 jobs.',
            type: 'job_search_results',
            matches: [{ title: 'HSE Manager', company: 'Dutco Group' }],
            options: [{ action: 'view_jobs', label: 'View jobs' }],
            next_actions: [{ action: 'save_search', label: 'Save search' }],
            success: true,
        });
        expect(result.success).toBe(true);
    });
});

// ── Empty agentic_ui ──────────────────────────────────────────────────────────

describe('RicoChatResponseSchema — empty agentic_ui', () => {
    it('accepts response with empty agentic_ui object', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'Hello.',
            agentic_ui: {},
        });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.agentic_ui).toBeDefined();
            expect(result.data.agentic_ui?.actions).toEqual([]);
            expect(result.data.agentic_ui?.permission_request).toBeUndefined();
            expect(result.data.agentic_ui?.progress).toEqual([]);
            expect(result.data.agentic_ui?.proposed_changes).toEqual([]);
            expect(result.data.agentic_ui?.attachment_analysis).toEqual([]);
        }
    });

    it('accepts response with fully defaulted agentic_ui', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'Hello.',
            agentic_ui: {
                actions: [],
                permission_request: null,
                progress: [],
                proposed_changes: [],
                attachment_analysis: [],
            },
        });
        expect(result.success).toBe(true);
    });
});

// ── Actions ───────────────────────────────────────────────────────────────────

describe('RicoChatResponseSchema — agentic_ui.actions', () => {
    it('accepts response with navigate action', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'Found 7 jobs.',
            agentic_ui: {
                actions: [
                    {
                        id: 'view-jobs',
                        label: 'View jobs',
                        kind: 'navigate',
                        impact: 'low',
                        requires_confirmation: false,
                        href: '/jobs',
                        payload: {},
                    },
                ],
            },
        });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.agentic_ui?.actions?.[0]?.id).toBe('view-jobs');
            expect(result.data.agentic_ui?.actions?.[0]?.kind).toBe('navigate');
        }
    });

    it('accepts submit action with endpoint and payload', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'Save this search?',
            agentic_ui: {
                actions: [
                    {
                        id: 'save-search',
                        label: 'Save search',
                        kind: 'submit',
                        endpoint: '/api/v1/rico/settings/saved-searches',
                        payload: { query: 'HSE Manager Dubai' },
                    },
                ],
            },
        });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.agentic_ui?.actions?.[0]?.payload).toEqual({ query: 'HSE Manager Dubai' });
        }
    });

    it('accepts all valid action kinds', () => {
        const kinds = ['navigate', 'submit', 'chat_continue', 'open_drawer', 'approve', 'cancel'] as const;
        for (const kind of kinds) {
            const result = RicoChatActionSchema.safeParse({ id: 'x', label: 'X', kind });
            expect(result.success).toBe(true);
        }
    });

    it('rejects invalid action kind', () => {
        const result = RicoChatActionSchema.safeParse({
            id: 'x',
            label: 'Bad action',
            kind: 'fly_to_moon',
        });
        expect(result.success).toBe(false);
    });
});

// ── Permission request ────────────────────────────────────────────────────────

describe('RicoChatResponseSchema — agentic_ui.permission_request', () => {
    it('accepts medium-risk permission without review_action', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'Save this search?',
            agentic_ui: {
                permission_request: {
                    id: 'perm-save',
                    title: 'Save search',
                    summary: 'Rico will save your current filters.',
                    risk_level: 'medium',
                    data_used: ['search filters'],
                    effects: ['Creates a saved search'],
                    approve_action: approveAction,
                    cancel_action: cancelAction,
                },
            },
        });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.agentic_ui?.permission_request?.risk_level).toBe('medium');
        }
    });

    it('accepts high-risk permission with review_action', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'Apply to this job?',
            agentic_ui: {
                permission_request: {
                    id: 'perm-apply',
                    title: 'Apply to HSE Manager — Dutco Group',
                    summary: 'Rico will submit your application.',
                    risk_level: 'high',
                    data_used: ['active CV', 'cover letter'],
                    effects: ['Submits application', 'Saves record'],
                    approve_action: approveAction,
                    review_action: {
                        id: 'review',
                        label: 'Review first',
                        kind: 'open_drawer',
                        impact: 'low',
                        requires_confirmation: false,
                        payload: {},
                    },
                    cancel_action: cancelAction,
                },
            },
        });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.agentic_ui?.permission_request?.risk_level).toBe('high');
            expect(result.data.agentic_ui?.permission_request?.review_action).toBeDefined();
        }
    });

    it('rejects low risk_level (only medium/high allowed)', () => {
        const result = RicoPermissionRequestSchema.safeParse({
            id: 'perm-x',
            title: 'Test',
            summary: 'Test',
            risk_level: 'low',
            approve_action: approveAction,
            cancel_action: cancelAction,
        });
        expect(result.success).toBe(false);
    });
});

// ── Progress steps ────────────────────────────────────────────────────────────

describe('RicoChatResponseSchema — agentic_ui.progress', () => {
    it('accepts all four progress statuses', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'Analyzing your upload...',
            agentic_ui: {
                progress: [
                    { id: 's1', label: 'Detecting file type', status: 'complete' },
                    { id: 's2', label: 'Reading text', status: 'running' },
                    { id: 's3', label: 'Classifying', status: 'pending' },
                    { id: 's4', label: 'Saving result', status: 'failed' },
                ],
            },
        });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.agentic_ui?.progress?.length).toBe(4);
            expect(result.data.agentic_ui?.progress?.[0]?.status).toBe('complete');
        }
    });

    it('rejects invalid progress status', () => {
        const result = RicoProgressStepSchema.safeParse({
            id: 's1',
            label: 'Step',
            status: 'unknown',
        });
        expect(result.success).toBe(false);
    });
});

// ── Proposed changes ──────────────────────────────────────────────────────────

describe('RicoChatResponseSchema — agentic_ui.proposed_changes', () => {
    it('accepts chat-sourced proposed changes', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'I can update your preferences.',
            agentic_ui: {
                proposed_changes: [
                    {
                        field: 'preferred_cities',
                        current_value: ['Abu Dhabi'],
                        proposed_value: ['Dubai', 'Sharjah'],
                        source: 'chat',
                    },
                    {
                        field: 'minimum_salary_aed',
                        current_value: null,
                        proposed_value: 15000,
                        source: 'chat',
                    },
                ],
            },
        });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.agentic_ui?.proposed_changes?.length).toBe(2);
        }
    });

    it('accepts all valid source values', () => {
        const sources = ['chat', 'cv', 'file', 'screenshot', 'system', 'user_action'] as const;
        for (const source of sources) {
            const result = RicoProposedChangeSchema.safeParse({
                field: 'test_field',
                proposed_value: 'test_value',
                source,
            });
            expect(result.success).toBe(true);
        }
    });

    it('rejects invalid source', () => {
        const result = RicoProposedChangeSchema.safeParse({
            field: 'x',
            proposed_value: 'y',
            source: 'email',
        });
        expect(result.success).toBe(false);
    });
});

// ── Attachment analysis ───────────────────────────────────────────────────────

describe('RicoChatResponseSchema — agentic_ui.attachment_analysis', () => {
    it('accepts job post screenshot analysis', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'I found a job post in this screenshot.',
            agentic_ui: {
                attachment_analysis: [
                    {
                        id: 'att-001',
                        filename: 'linkedin_screenshot.png',
                        mime_type: 'image/png',
                        purpose: 'job_post',
                        confidence: 0.82,
                        extracted_summary: 'QHSE Manager role at Example Group',
                        extracted_fields: { title: 'QHSE Manager', company: 'Example Group' },
                        warnings: ['Salary not visible'],
                    },
                ],
            },
        });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.agentic_ui?.attachment_analysis?.[0]?.purpose).toBe('job_post');
        }
    });

    it('accepts all ten attachment purposes', () => {
        const purposes = [
            'cv_resume', 'job_post', 'recruiter_message', 'application_form',
            'certificate', 'offer_letter', 'contract_or_legalish',
            'company_profile', 'public_comment', 'unknown_document',
        ] as const;
        for (const purpose of purposes) {
            const result = RicoAttachmentAnalysisSchema.safeParse({
                id: 'att-x',
                purpose,
                confidence: 0.5,
            });
            expect(result.success).toBe(true);
        }
    });

    it('rejects invalid attachment purpose', () => {
        const result = RicoAttachmentAnalysisSchema.safeParse({
            id: 'att-x',
            purpose: 'banana_document',
            confidence: 0.5,
        });
        expect(result.success).toBe(false);
    });
});

// ── Full payload ──────────────────────────────────────────────────────────────

describe('RicoChatResponseSchema — fully populated agentic_ui', () => {
    it('accepts response with all agentic_ui fields', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'Here is your analysis.',
            type: 'document_analysis',
            agentic_ui: {
                actions: [
                    {
                        id: 'save-opp',
                        label: 'Save opportunity',
                        kind: 'submit',
                        impact: 'low',
                        requires_confirmation: false,
                        payload: { job_id: 'j-123' },
                    },
                ],
                permission_request: null,
                progress: [
                    { id: 'p1', label: 'Analyzing upload', status: 'complete' },
                ],
                proposed_changes: [
                    {
                        field: 'target_roles',
                        current_value: null,
                        proposed_value: ['QHSE Manager'],
                        source: 'file',
                    },
                ],
                attachment_analysis: [
                    {
                        id: 'att-002',
                        filename: 'cv.pdf',
                        purpose: 'cv_resume',
                        confidence: 0.97,
                        extracted_fields: { name: 'Ahmed' },
                        warnings: [],
                    },
                ],
            },
        });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.agentic_ui?.actions?.[0]?.id).toBe('save-opp');
            expect(result.data.agentic_ui?.progress?.[0]?.status).toBe('complete');
            expect(result.data.agentic_ui?.proposed_changes?.[0]?.field).toBe('target_roles');
            expect(result.data.agentic_ui?.attachment_analysis?.[0]?.purpose).toBe('cv_resume');
        }
    });

    it('legacy fields coexist with agentic_ui without conflict', () => {
        const result = RicoChatResponseSchema.safeParse({
            message: 'Found jobs.',
            type: 'job_search_results',
            matches: [{ title: 'HSE Manager', company: 'Dutco Group' }],
            next_actions: [{ action: 'view_jobs', label: 'View jobs' }],
            success: true,
            agentic_ui: {
                actions: [{ id: 'view', label: 'View jobs', kind: 'navigate' }],
            },
        });
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.matches?.[0]?.title).toBe('HSE Manager');
            expect(result.data.agentic_ui?.actions?.[0]?.id).toBe('view');
        }
    });
});
