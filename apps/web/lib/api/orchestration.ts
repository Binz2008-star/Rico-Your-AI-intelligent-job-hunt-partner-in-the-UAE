import { agentApi, ricoChatApi } from './client';

export interface CommandResponse {
  success: boolean;
  message: string;
  data?: unknown;
}

export interface TrajectoryForecast {
  nodes: Array<{
    id: string;
    title: string;
    probability: number;
    timeline: string;
  }>;
  currentPhase: string;
}

export interface OpportunitySignal {
  id: string;
  company: string;
  role: string;
  matchScore: number;
  momentum: 'high' | 'medium' | 'low';
  location: string;
  timestamp: string;
}

const EMPTY_TRAJECTORY: TrajectoryForecast = {
  nodes: [],
  currentPhase: 'live-backend-pending',
};

const EMPTY_SIGNALS: OpportunitySignal[] = [];

export const orchestrationApi = {
  executeCommand: async (command: string): Promise<CommandResponse> => {
    const response = await agentApi.chat({ message: command });
    return {
      success: response.success,
      message: response.message,
      data: {
        actions: response.actions,
        ui: response.ui,
        tool_used: response.tool_used,
        execution_time_ms: response.execution_time_ms,
      },
    };
  },

  getTrajectory: async (): Promise<TrajectoryForecast> => {
    return EMPTY_TRAJECTORY;
  },

  getSignals: async (): Promise<OpportunitySignal[]> => {
    return EMPTY_SIGNALS;
  },

  uploadCV: async (file: File): Promise<unknown> => {
    return ricoChatApi.uploadCV(file);
  },
};
