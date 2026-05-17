import { orchestrationApi } from '@/lib/api/orchestration';
import { useOrchestrationStore } from '@/lib/store/useOrchestrationStore';
import { useEffect, useState } from 'react';

export function useOrchestration() {
    const { trajectory, signals, addTrajectoryNode, addSignal, isProcessing } = useOrchestrationStore();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchTrajectory = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await orchestrationApi.getTrajectory();
            data.nodes.forEach((node) => addTrajectoryNode(node as any));
        } catch (err) {
            setError('Failed to fetch trajectory data');
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchSignals = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await orchestrationApi.getSignals();
            data.forEach(addSignal);
        } catch (err) {
            setError('Failed to fetch signals');
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    const executeCommand = async (command: string) => {
        setError(null);
        try {
            const response = await orchestrationApi.executeCommand(command);
            return response;
        } catch (err) {
            setError('Failed to execute command');
            console.error(err);
            throw err;
        }
    };

    useEffect(() => {
        fetchTrajectory();
        fetchSignals();
    }, []);

    return {
        trajectory,
        signals,
        isLoading,
        isProcessing,
        error,
        executeCommand,
        refetchTrajectory: fetchTrajectory,
        refetchSignals: fetchSignals,
    };
}
