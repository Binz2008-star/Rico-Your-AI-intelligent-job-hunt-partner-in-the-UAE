/**
 * Memory Persistence Layer for Rico AI
 * Uses IndexedDB for client-side storage of longitudinal memory,
 * trajectory history, recruiter interactions, compensation targets,
 * strategic preferences, and opportunity weighting.
 */

import type {
    CompensationTarget,
    LongitudinalMemory,
    OpportunityWeighting,
    RecruiterInteraction,
    StrategicPreference,
    TrajectoryHistory,
} from '@/lib/schemas';
import { DBSchema, IDBPDatabase, openDB } from 'idb';

// ============================================================================
// Database Schema
// ============================================================================

interface RicoMemoryDB extends DBSchema {
    longitudinal_memory: {
        key: string;
        value: LongitudinalMemory & { id: string };
        indexes: {
            'by-user-id': string;
            'by-timestamp': string;
            'by-event-type': string;
        };
    };
    trajectory_history: {
        key: string;
        value: TrajectoryHistory & { id: string };
        indexes: {
            'by-user-id': string;
            'by-timestamp': string;
        };
    };
    recruiter_interactions: {
        key: string;
        value: RecruiterInteraction & { id: string };
        indexes: {
            'by-user-id': string;
            'by-recruiter-id': string;
            'by-company': string;
            'by-timestamp': string;
        };
    };
    compensation_targets: {
        key: string;
        value: CompensationTarget & { id: string };
        indexes: {
            'by-user-id': string;
            'by-timestamp': string;
        };
    };
    strategic_preferences: {
        key: string;
        value: StrategicPreference & { id: string };
        indexes: {
            'by-user-id': string;
            'by-timestamp': string;
        };
    };
    opportunity_weighting: {
        key: string;
        value: OpportunityWeighting & { id: string };
        indexes: {
            'by-user-id': string;
            'by-opportunity-id': string;
            'by-timestamp': string;
        };
    };
}

const DB_NAME = 'RicoMemoryDB';
const DB_VERSION = 1;

let db: IDBPDatabase<RicoMemoryDB> | null = null;

// ============================================================================
// Database Initialization
// ============================================================================

async function getDB(): Promise<IDBPDatabase<RicoMemoryDB>> {
    if (db) return db;

    db = await openDB<RicoMemoryDB>(DB_NAME, DB_VERSION, {
        upgrade(db: IDBPDatabase<RicoMemoryDB>) {
            // Longitudinal memory store
            if (!db.objectStoreNames.contains('longitudinal_memory')) {
                const store = db.createObjectStore('longitudinal_memory', { keyPath: 'id' });
                store.createIndex('by-user-id', 'user_id');
                store.createIndex('by-timestamp', 'timestamp');
                store.createIndex('by-event-type', 'event_type');
            }

            // Trajectory history store
            if (!db.objectStoreNames.contains('trajectory_history')) {
                const store = db.createObjectStore('trajectory_history', { keyPath: 'id' });
                store.createIndex('by-user-id', 'user_id');
                store.createIndex('by-timestamp', 'timestamp');
            }

            // Recruiter interactions store
            if (!db.objectStoreNames.contains('recruiter_interactions')) {
                const store = db.createObjectStore('recruiter_interactions', { keyPath: 'id' });
                store.createIndex('by-user-id', 'user_id');
                store.createIndex('by-recruiter-id', 'recruiter_id');
                store.createIndex('by-company', 'company');
                store.createIndex('by-timestamp', 'timestamp');
            }

            // Compensation targets store
            if (!db.objectStoreNames.contains('compensation_targets')) {
                const store = db.createObjectStore('compensation_targets', { keyPath: 'id' });
                store.createIndex('by-user-id', 'user_id');
                store.createIndex('by-timestamp', 'timestamp');
            }

            // Strategic preferences store
            if (!db.objectStoreNames.contains('strategic_preferences')) {
                const store = db.createObjectStore('strategic_preferences', { keyPath: 'id' });
                store.createIndex('by-user-id', 'user_id');
                store.createIndex('by-timestamp', 'timestamp');
            }

            // Opportunity weighting store
            if (!db.objectStoreNames.contains('opportunity_weighting')) {
                const store = db.createObjectStore('opportunity_weighting', { keyPath: 'id' });
                store.createIndex('by-user-id', 'user_id');
                store.createIndex('by-opportunity-id', 'opportunity_id');
                store.createIndex('by-timestamp', 'timestamp');
            }
        },
    });

    return db;
}

// ============================================================================
// Longitudinal Memory
// ============================================================================

export const longitudinalMemoryApi = {
    add: async (memory: LongitudinalMemory): Promise<string> => {
        const db = await getDB();
        const id = `${memory.user_id}-${memory.timestamp}-${memory.event_type}`;
        await db.put('longitudinal_memory', { ...memory, id });
        return id;
    },

    getByUserId: async (userId: string, limit = 100): Promise<LongitudinalMemory[]> => {
        const db = await getDB();
        return db.getAllFromIndex('longitudinal_memory', 'by-user-id', userId);
    },

    getByEventType: async (userId: string, eventType: LongitudinalMemory['event_type']): Promise<LongitudinalMemory[]> => {
        const db = await getDB();
        const all = await db.getAllFromIndex('longitudinal_memory', 'by-user-id', userId);
        return all.filter(m => m.event_type === eventType);
    },

    getByTimeRange: async (userId: string, start: string, end: string): Promise<LongitudinalMemory[]> => {
        const db = await getDB();
        const all = await db.getAllFromIndex('longitudinal_memory', 'by-user-id', userId);
        return all.filter(m => m.timestamp >= start && m.timestamp <= end);
    },

    getRecent: async (userId: string, limit = 50): Promise<LongitudinalMemory[]> => {
        const db = await getDB();
        const all = await db.getAllFromIndex('longitudinal_memory', 'by-user-id', userId);
        return all
            .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
            .slice(0, limit);
    },
};

// ============================================================================
// Trajectory History
// ============================================================================

export const trajectoryHistoryApi = {
    add: async (history: TrajectoryHistory): Promise<string> => {
        const db = await getDB();
        const id = `${history.user_id}-${history.timestamp}`;
        await db.put('trajectory_history', { ...history, id });
        return id;
    },

    getByUserId: async (userId: string): Promise<TrajectoryHistory[]> => {
        const db = await getDB();
        return db.getAllFromIndex('trajectory_history', 'by-user-id', userId);
    },

    getLatest: async (userId: string): Promise<TrajectoryHistory | null> => {
        const db = await getDB();
        const all = await db.getAllFromIndex('trajectory_history', 'by-user-id', userId);
        if (all.length === 0) return null;
        return all.sort((a: TrajectoryHistory, b: TrajectoryHistory) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0];
    },
};

// ============================================================================
// Recruiter Interactions
// ============================================================================

export const recruiterInteractionApi = {
    add: async (interaction: RecruiterInteraction): Promise<string> => {
        const db = await getDB();
        const id = `${interaction.user_id}-${interaction.recruiter_id}-${interaction.timestamp}`;
        await db.put('recruiter_interactions', { ...interaction, id });
        return id;
    },

    getByUserId: async (userId: string): Promise<RecruiterInteraction[]> => {
        const db = await getDB();
        return db.getAllFromIndex('recruiter_interactions', 'by-user-id', userId);
    },

    getByRecruiterId: async (recruiterId: string): Promise<RecruiterInteraction[]> => {
        const db = await getDB();
        return db.getAllFromIndex('recruiter_interactions', 'by-recruiter-id', recruiterId);
    },

    getByCompany: async (company: string): Promise<RecruiterInteraction[]> => {
        const db = await getDB();
        return db.getAllFromIndex('recruiter_interactions', 'by-company', company);
    },

    getRecent: async (userId: string, limit = 50): Promise<RecruiterInteraction[]> => {
        const db = await getDB();
        const all = await db.getAllFromIndex('recruiter_interactions', 'by-user-id', userId);
        return all
            .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
            .slice(0, limit);
    },
};

// ============================================================================
// Compensation Targets
// ============================================================================

export const compensationTargetApi = {
    add: async (target: CompensationTarget): Promise<string> => {
        const db = await getDB();
        const id = `${target.user_id}-${target.timestamp}`;
        await db.put('compensation_targets', { ...target, id });
        return id;
    },

    getByUserId: async (userId: string): Promise<CompensationTarget[]> => {
        const db = await getDB();
        return db.getAllFromIndex('compensation_targets', 'by-user-id', userId);
    },

    getLatest: async (userId: string): Promise<CompensationTarget | null> => {
        const db = await getDB();
        const all = await db.getAllFromIndex('compensation_targets', 'by-user-id', userId);
        if (all.length === 0) return null;
        return all.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0];
    },
};

// ============================================================================
// Strategic Preferences
// ============================================================================

export const strategicPreferenceApi = {
    add: async (preference: StrategicPreference): Promise<string> => {
        const db = await getDB();
        const id = `${preference.user_id}-${preference.timestamp}`;
        await db.put('strategic_preferences', { ...preference, id });
        return id;
    },

    getByUserId: async (userId: string): Promise<StrategicPreference[]> => {
        const db = await getDB();
        return db.getAllFromIndex('strategic_preferences', 'by-user-id', userId);
    },

    getLatest: async (userId: string): Promise<StrategicPreference | null> => {
        const db = await getDB();
        const all = await db.getAllFromIndex('strategic_preferences', 'by-user-id', userId);
        if (all.length === 0) return null;
        return all.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0];
    },

    update: async (preference: StrategicPreference): Promise<string> => {
        const db = await getDB();
        const id = `${preference.user_id}-${preference.timestamp}`;
        await db.put('strategic_preferences', { ...preference, id });
        return id;
    },
};

// ============================================================================
// Opportunity Weighting
// ============================================================================

export const opportunityWeightingApi = {
    add: async (weighting: OpportunityWeighting): Promise<string> => {
        const db = await getDB();
        const id = `${weighting.user_id}-${weighting.opportunity_id}-${weighting.timestamp}`;
        await db.put('opportunity_weighting', { ...weighting, id });
        return id;
    },

    getByUserId: async (userId: string): Promise<OpportunityWeighting[]> => {
        const db = await getDB();
        return db.getAllFromIndex('opportunity_weighting', 'by-user-id', userId);
    },

    getByOpportunityId: async (opportunityId: string): Promise<OpportunityWeighting[]> => {
        const db = await getDB();
        return db.getAllFromIndex('opportunity_weighting', 'by-opportunity-id', opportunityId);
    },

    getLatest: async (userId: string, opportunityId: string): Promise<OpportunityWeighting | null> => {
        const db = await getDB();
        const all = await db.getAllFromIndex('opportunity_weighting', 'by-user-id', userId);
        const filtered = all.filter(w => w.opportunity_id === opportunityId);
        if (filtered.length === 0) return null;
        return filtered.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0];
    },
};

// ============================================================================
// Memory Analytics
// ============================================================================

export const memoryAnalytics = {
    getEventFrequency: async (userId: string): Promise<Record<string, number>> => {
        const memories = await longitudinalMemoryApi.getByUserId(userId);
        const frequency: Record<string, number> = {};

        memories.forEach(memory => {
            frequency[memory.event_type] = (frequency[memory.event_type] || 0) + 1;
        });

        return frequency;
    },

    getRecruiterResponseRate: async (userId: string): Promise<Record<string, number>> => {
        const interactions = await recruiterInteractionApi.getByUserId(userId);
        const responseRates: Record<string, number> = {};

        const recruiterInteractions: Record<string, RecruiterInteraction[]> = {};
        interactions.forEach(interaction => {
            if (!recruiterInteractions[interaction.recruiter_id]) {
                recruiterInteractions[interaction.recruiter_id] = [];
            }
            recruiterInteractions[interaction.recruiter_id].push(interaction);
        });

        Object.entries(recruiterInteractions).forEach(([recruiterId, recs]) => {
            const total = recs.length;
            const positive = recs.filter(r => r.outcome === 'positive' || r.outcome === 'offer').length;
            responseRates[recruiterId] = total > 0 ? positive / total : 0;
        });

        return responseRates;
    },

    getCompensationTrajectory: async (userId: string): Promise<Array<{ timestamp: string; total_compensation: number }>> => {
        const targets = await compensationTargetApi.getByUserId(userId);
        return targets
            .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
            .map(t => ({
                timestamp: t.timestamp,
                total_compensation: t.target.total_compensation,
            }));
    },
};
