import {
    AgentChatRequestSchema,
    AgentUIResponseSchema,
    ApplicationCreateRequestSchema,
    ApplicationListResponseSchema,
    JobActionRequestSchema,
    JobActionResponseSchema,
    JobListResponseSchema,
    LoginRequestSchema,
    LoginResponseSchema,
    ManualApplicationCreateRequestSchema,
    PipelineStatusResponseSchema,
    PipelineTriggerResponseSchema,
    RegisterRequestSchema,
    RegisterResponseSchema,
    RicoChatRequestSchema,
    RicoFeedbackRequestSchema,
    RicoPublicChatRequestSchema,
    SettingsResponseSchema,
    SettingsUpdateRequestSchema,
    StatsResponseSchema,
    StatusUpdateRequestSchema,
    StatusUpdateResponseSchema,
    type AgentChatRequest,
    type AgentUIResponse,
    type ApplicationCreateRequest,
    type ApplicationListResponse,
    type JobActionRequest,
    type JobActionResponse,
    type JobListResponse,
    type LoginRequest,
    type LoginResponse,
    type ManualApplicationCreateRequest,
    type PipelineStatusResponse,
    type PipelineTriggerResponse,
    type RegisterRequest,
    type RegisterResponse,
    type RicoChatRequest,
    type RicoFeedbackRequest,
    type RicoPublicChatRequest,
    type SettingsResponse,
    type SettingsUpdateRequest,
    type StatsResponse,
    type StatusUpdateRequest,
    type StatusUpdateResponse,
} from '@/lib/schemas';
import axios from 'axios';
import { z } from 'zod';

const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_RICO_API ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:8000';
const API_PROXY_BASE_URL = '/proxy';
const RESOLVED_BASE_URL = typeof window === 'undefined' ? API_BASE_URL : API_PROXY_BASE_URL;

function validateResponse<T>(schema: z.ZodType<T>, data: unknown, context: string): T {
    const parsed = schema.safeParse(data);
    if (!parsed.success) {
        throw new Error(`Invalid ${context} response: ${parsed.error.message}`);
    }
    return parsed.data;
}

export const apiClient = axios.create({
    baseURL: RESOLVED_BASE_URL,
    withCredentials: true,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401 && typeof window !== 'undefined') {
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

// ============================================================================
// Auth API
// ============================================================================

export const authApi = {
    login: async (data: LoginRequest): Promise<LoginResponse> => {
        const payload = LoginRequestSchema.parse(data);
        const response = await apiClient.post('/api/v1/auth/login', payload);
        return validateResponse(LoginResponseSchema, response.data, 'login');
    },

    register: async (data: RegisterRequest): Promise<RegisterResponse> => {
        const payload = RegisterRequestSchema.parse(data);
        const response = await apiClient.post('/api/v1/auth/register', payload);
        return validateResponse(RegisterResponseSchema, response.data, 'register');
    },

    logout: async (): Promise<void> => {
        await apiClient.post('/api/v1/auth/logout');
    },

    refreshToken: async (): Promise<void> => {
        throw new Error('Backend auth refresh is not implemented. Use the access_token cookie session.');
    },
};

// ============================================================================
// Jobs API
// ============================================================================

export const jobsApi = {
    list: async (params?: { page?: number; limit?: number; min_score?: number; source?: string }): Promise<JobListResponse> => {
        const response = await apiClient.get('/api/v1/jobs', { params });
        return validateResponse(JobListResponseSchema, response.data, 'jobs list');
    },

    getById: async (jobId: string): Promise<any> => {
        const response = await apiClient.get(`/api/v1/jobs/${jobId}`);
        return response.data;
    },

    apply: async (jobId: string, data?: JobActionRequest): Promise<JobActionResponse> => {
        const payload = data ? JobActionRequestSchema.parse(data) : undefined;
        const response = await apiClient.post(`/api/v1/jobs/${jobId}/apply`, payload);
        return validateResponse(JobActionResponseSchema, response.data, 'job apply');
    },

    skip: async (jobId: string, data?: JobActionRequest): Promise<JobActionResponse> => {
        const payload = data ? JobActionRequestSchema.parse(data) : undefined;
        const response = await apiClient.post(`/api/v1/jobs/${jobId}/skip`, payload);
        return validateResponse(JobActionResponseSchema, response.data, 'job skip');
    },

    save: async (jobId: string, data?: JobActionRequest): Promise<JobActionResponse> => {
        const payload = data ? JobActionRequestSchema.parse(data) : undefined;
        const response = await apiClient.post(`/api/v1/jobs/${jobId}/save`, payload);
        return validateResponse(JobActionResponseSchema, response.data, 'job save');
    },

    block: async (jobId: string, data?: JobActionRequest): Promise<JobActionResponse> => {
        const payload = data ? JobActionRequestSchema.parse(data) : undefined;
        const response = await apiClient.post(`/api/v1/jobs/${jobId}/block`, payload);
        return validateResponse(JobActionResponseSchema, response.data, 'job block');
    },
};

// ============================================================================
// Applications API
// ============================================================================

export const applicationsApi = {
    create: async (data: ApplicationCreateRequest): Promise<StatusUpdateResponse> => {
        const payload = ApplicationCreateRequestSchema.parse(data);
        const response = await apiClient.post('/api/v1/applications', payload);
        return validateResponse(StatusUpdateResponseSchema, response.data, 'application create');
    },

    createManual: async (data: ManualApplicationCreateRequest): Promise<StatusUpdateResponse> => {
        const payload = ManualApplicationCreateRequestSchema.parse(data);
        const response = await apiClient.post('/api/v1/applications/manual', payload);
        return validateResponse(StatusUpdateResponseSchema, response.data, 'manual application create');
    },

    list: async (params?: { status?: string; page?: number; limit?: number }): Promise<ApplicationListResponse> => {
        const response = await apiClient.get('/api/v1/applications', { params });
        return validateResponse(ApplicationListResponseSchema, response.data, 'applications list');
    },

    update: async (jobId: string, data: StatusUpdateRequest): Promise<StatusUpdateResponse> => {
        const payload = StatusUpdateRequestSchema.parse(data);
        const response = await apiClient.patch(`/api/v1/applications/${jobId}`, payload);
        return validateResponse(StatusUpdateResponseSchema, response.data, 'application update');
    },

    getStats: async (): Promise<any> => {
        const response = await apiClient.get('/api/v1/applications/stats');
        return response.data;
    },
};

// ============================================================================
// Pipeline API
// ============================================================================

export const pipelineApi = {
    getStatus: async (): Promise<PipelineStatusResponse> => {
        const response = await apiClient.get('/api/v1/pipeline/status');
        return validateResponse(PipelineStatusResponseSchema, response.data, 'pipeline status');
    },

    trigger: async (): Promise<PipelineTriggerResponse> => {
        const response = await apiClient.post('/api/v1/pipeline/trigger');
        return validateResponse(PipelineTriggerResponseSchema, response.data, 'pipeline trigger');
    },
};

// ============================================================================
// Stats API
// ============================================================================

export const statsApi = {
    get: async (): Promise<StatsResponse> => {
        const response = await apiClient.get('/api/v1/stats');
        return validateResponse(StatsResponseSchema, response.data, 'stats');
    },
};

// ============================================================================
// Settings API
// ============================================================================

export const settingsApi = {
    get: async (): Promise<SettingsResponse> => {
        const response = await apiClient.get('/api/v1/settings');
        return validateResponse(SettingsResponseSchema, response.data, 'settings');
    },

    update: async (data: SettingsUpdateRequest): Promise<SettingsResponse> => {
        const payload = SettingsUpdateRequestSchema.parse(data);
        const response = await apiClient.put('/api/v1/settings', payload);
        return validateResponse(SettingsResponseSchema, response.data, 'settings update');
    },
};

// ============================================================================
// Agent API
// ============================================================================

export const agentApi = {
    chat: async (data: AgentChatRequest): Promise<AgentUIResponse> => {
        const payload = AgentChatRequestSchema.parse(data);
        const response = await apiClient.post('/api/v1/agent/chat', payload);
        return validateResponse(AgentUIResponseSchema, response.data, 'agent chat');
    },
};

// ============================================================================
// Rico Chat API
// ============================================================================

export const ricoChatApi = {
    chat: async (data: RicoChatRequest): Promise<any> => {
        const payload = RicoChatRequestSchema.parse(data);
        const response = await apiClient.post('/api/v1/rico/chat', payload);
        return response.data;
    },

    publicChat: async (data: RicoPublicChatRequest): Promise<any> => {
        const payload = RicoPublicChatRequestSchema.parse(data);
        const response = await apiClient.post('/api/v1/rico/chat/public', payload);
        return response.data;
    },

    getProfile: async (): Promise<any> => {
        const response = await apiClient.get('/api/v1/rico/profile');
        return response.data;
    },

    getChatHistory: async (): Promise<any> => {
        const response = await apiClient.get('/api/v1/rico/chat/history');
        return response.data;
    },

    uploadCV: async (file: File): Promise<any> => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await apiClient.post('/api/v1/rico/upload-cv', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
    },

    submitFeedback: async (data: RicoFeedbackRequest): Promise<any> => {
        const payload = RicoFeedbackRequestSchema.parse(data);
        const response = await apiClient.post('/api/v1/rico/feedback', payload);
        return response.data;
    },
};

export default apiClient;
