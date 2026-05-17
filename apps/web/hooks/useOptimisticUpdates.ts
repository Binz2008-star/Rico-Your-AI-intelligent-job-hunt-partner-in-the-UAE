/**
 * Optimistic Updates Hook
 * Provides instant UI feedback for orchestration actions while backend requests complete.
 * Handles rollback on failure and maintains consistency with server state.
 */

import { applicationsApi, jobsApi, pipelineApi } from '@/lib/api/client';
import { useCallback, useState } from 'react';

export interface OptimisticUpdateState<T> {
    data: T | null;
    isPending: boolean;
    error: Error | null;
}

export interface OptimisticAction<T> {
    execute: () => Promise<T>;
    rollback: () => void;
    optimisticUpdate: (previous: T) => T;
}

export interface OptimisticActionWithResult<TState, TResult> extends Omit<OptimisticAction<TState>, 'execute'> {
    execute: () => Promise<TResult>;
}

export function useOptimisticUpdate<T>(
    initialData: T | null,
) {
    const [state, setState] = useState<OptimisticUpdateState<T>>({
        data: initialData,
        isPending: false,
        error: null,
    });

    const executeOptimistic = useCallback(
        async <R>(action: OptimisticActionWithResult<T, R>): Promise<R> => {
            setState(prev => ({
                ...prev,
                isPending: true,
                error: null,
                data: prev.data !== null ? action.optimisticUpdate(prev.data) : null,
            }));

            try {
                const result = await action.execute();
                setState({
                    data: null, // Will be refreshed by caller
                    isPending: false,
                    error: null,
                });
                return result;
            } catch (error) {
                action.rollback();
                setState(prev => ({
                    ...prev,
                    isPending: false,
                    error: error as Error,
                    data: prev.data, // Revert to optimistic state before rollback
                }));
                throw error;
            }
        },
        [],
    );

    return { state, executeOptimistic, setState };
}

// ============================================================================
// Job Action Optimistic Updates
// ============================================================================

export function useJobOptimisticUpdates(jobId: string) {
    const { state, executeOptimistic, setState } = useOptimisticUpdate<any>(null);

    const applyToJob = useCallback(async (jobData?: any) => {
        const previousData = state.data;

        return executeOptimistic({
            execute: () => jobsApi.apply(jobId, jobData ? { job: jobData } : undefined),
            rollback: () => {
                // Rollback handled by state restoration
            },
            optimisticUpdate: (prev: any) => ({
                ...prev,
                status: 'applied',
                applied_at: new Date().toISOString(),
            }),
        });
    }, [jobId, state.data, executeOptimistic]);

    const skipJob = useCallback(async (jobData?: any) => {
        return executeOptimistic({
            execute: () => jobsApi.skip(jobId, jobData ? { job: jobData } : undefined),
            rollback: () => { },
            optimisticUpdate: (prev: any) => ({
                ...prev,
                status: 'skipped',
                skipped_at: new Date().toISOString(),
            }),
        });
    }, [jobId, executeOptimistic]);

    const saveJob = useCallback(async (jobData?: any) => {
        return executeOptimistic({
            execute: () => jobsApi.save(jobId, jobData ? { job: jobData } : undefined),
            rollback: () => { },
            optimisticUpdate: (prev: any) => ({
                ...prev,
                status: 'saved',
                saved_at: new Date().toISOString(),
            }),
        });
    }, [jobId, executeOptimistic]);

    const blockCompany = useCallback(async (jobData?: any) => {
        return executeOptimistic({
            execute: () => jobsApi.block(jobId, jobData ? { job: jobData } : undefined),
            rollback: () => { },
            optimisticUpdate: (prev: any) => ({
                ...prev,
                status: 'blocked',
                blocked_at: new Date().toISOString(),
            }),
        });
    }, [jobId, executeOptimistic]);

    return {
        state,
        applyToJob,
        skipJob,
        saveJob,
        blockCompany,
        setData: setState,
    };
}

// ============================================================================
// Application Status Optimistic Updates
// ============================================================================

export function useApplicationOptimisticUpdates(jobId: string) {
    const { state, executeOptimistic, setState } = useOptimisticUpdate<any>(null);

    const updateStatus = useCallback(async (
        status: string,
        notes?: string,
    ) => {
        return executeOptimistic({
            execute: () => applicationsApi.update(jobId, { status, notes }),
            rollback: () => { },
            optimisticUpdate: (prev: any) => ({
                ...prev,
                status,
                notes: notes || prev.notes,
                updated_at: new Date().toISOString(),
            }),
        });
    }, [jobId, executeOptimistic]);

    const createApplication = useCallback(async (jobData: any) => {
        return executeOptimistic({
            execute: () => applicationsApi.create(jobData),
            rollback: () => { },
            optimisticUpdate: (prev: any) => ({
                ...prev,
                status: 'opened',
                created_at: new Date().toISOString(),
                ...jobData,
            }),
        });
    }, [executeOptimistic]);

    return {
        state,
        updateStatus,
        createApplication,
        setData: setState,
    };
}

// ============================================================================
// Pipeline Optimistic Updates
// ============================================================================

export function usePipelineOptimisticUpdates() {
    const { state, executeOptimistic, setState } = useOptimisticUpdate<any>(null);

    const triggerPipeline = useCallback(async () => {
        return executeOptimistic({
            execute: () => pipelineApi.trigger(),
            rollback: () => { },
            optimisticUpdate: (prev: any) => ({
                ...prev,
                status: 'running',
                started_at: new Date().toISOString(),
                jobs_found: 0,
            }),
        });
    }, [executeOptimistic]);

    const refreshStatus = useCallback(async () => {
        const status = await pipelineApi.getStatus();
        setState({ data: status, isPending: false, error: null });
        return status;
    }, [setState]);

    return {
        state,
        triggerPipeline,
        refreshStatus,
        setData: setState,
    };
}

// ============================================================================
// Batch Optimistic Updates
// ============================================================================

export interface BatchOptimisticAction<T extends { id: string }> {
    id: string;
    execute: () => Promise<any>;
    optimisticUpdate: (previous: T) => T;
}

export function useBatchOptimisticUpdates<T extends { id: string }>(initialData: T[]) {
    const [state, setState] = useState<{
        data: T[];
        pending: Set<string>;
        errors: Map<string, Error>;
    }>({
        data: initialData,
        pending: new Set(),
        errors: new Map(),
    });

    const executeBatch = useCallback(async (
        actions: BatchOptimisticAction<T>[],
    ) => {
        const pendingIds = new Set(actions.map(a => a.id));

        // Apply optimistic updates
        const optimisticData = state.data.map(item => {
            const action = actions.find(a => a.id === (item as any).id);
            return action ? action.optimisticUpdate(item) : item;
        });

        setState(prev => ({
            ...prev,
            data: optimisticData,
            pending: new Set([...prev.pending, ...pendingIds]),
            errors: new Map(),
        }));

        // Execute actions
        const results = await Promise.allSettled(
            actions.map(async action => {
                try {
                    await action.execute();
                    return { id: action.id, success: true };
                } catch (error) {
                    return { id: action.id, success: false, error: error as Error };
                }
            }),
        );

        // Process results
        const newErrors = new Map<string, Error>();
        const failedIds = new Set<string>();

        results.forEach(result => {
            if (result.status === 'fulfilled' && !result.value.success) {
                newErrors.set(result.value.id, result.value.error!);
                failedIds.add(result.value.id);
            }
        });

        // Remove pending IDs
        const remainingPending = new Set(pendingIds);
        failedIds.forEach(id => remainingPending.delete(id));

        setState(prev => ({
            ...prev,
            pending: remainingPending,
            errors: new Map([...prev.errors, ...newErrors]),
        }));

        return {
            successful: results.filter(r => r.status === 'fulfilled' && (r.value as any).success).length,
            failed: failedIds.size,
            errors: newErrors,
        };
    }, [state.data]);

    const clearErrors = useCallback(() => {
        setState(prev => ({ ...prev, errors: new Map() }));
    }, []);

    return {
        state,
        executeBatch,
        clearErrors,
        setData: setState,
    };
}

// ============================================================================
// Optimistic Update Utilities
// ============================================================================

export function createOptimisticUpdater<T>(
    updateFn: (item: T) => T,
) {
    return (previous: T) => updateFn(previous);
}

export function createBatchUpdater<T extends { id: string }>(
    ids: string[],
    updateFn: (item: T) => T,
) {
    return (items: T[]) => {
        return items.map(item =>
            ids.includes(item.id) ? updateFn(item) : item
        );
    };
}

export function createConditionalUpdater<T>(
    condition: (item: T) => boolean,
    updateFn: (item: T) => T,
) {
    return (items: T[]) => {
        return items.map(item =>
            condition(item) ? updateFn(item) : item
        );
    };
}
