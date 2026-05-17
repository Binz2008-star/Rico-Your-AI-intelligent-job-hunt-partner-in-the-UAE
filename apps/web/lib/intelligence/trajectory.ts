/**
 * Trajectory Intelligence Engine
 * Uses memory data to forecast career trajectories, calculate momentum,
 * weight recruiter signals, detect convergence, and provide strategic positioning.
 */

import {
    compensationTargetApi,
    longitudinalMemoryApi,
    memoryAnalytics,
    opportunityWeightingApi,
    recruiterInteractionApi,
    strategicPreferenceApi,
    trajectoryHistoryApi,
} from '@/lib/memory';
import type {
    CompensationTarget,
    RecruiterInteraction,
    StrategicPreference,
    TrajectoryHistory
} from '@/lib/schemas';

// ============================================================================
// Trajectory Forecasting Models
// ============================================================================

export interface TrajectoryForecast {
    current_role: string;
    target_roles: string[];
    career_stage: 'early' | 'mid' | 'senior' | 'executive';
    momentum_score: number; // 0-1
    convergence_probability: number; // 0-1
    strategic_positioning: {
        market_fit: number; // 0-1
        skill_alignment: number; // 0-1
        opportunity_density: number; // 0-1
    };
    forecasted_nodes: TrajectoryNode[];
    time_horizon_months: number;
}

export interface TrajectoryNode {
    id: string;
    type: 'opportunity' | 'milestone' | 'decision' | 'outcome';
    title: string;
    probability: number; // 0-1
    timing: {
        optimal: string; // ISO date
        window_start: string; // ISO date
        window_end: string; // ISO date
        decay_rate: number; // 0-1 per month
    };
    strategic_importance: number; // 0-1
}

export class TrajectoryForecaster {
    /**
     * Generate a career trajectory forecast based on historical data and preferences
     */
    async forecast(userId: string, timeHorizonMonths = 12): Promise<TrajectoryForecast> {
        const [history, preferences, compensation] = await Promise.all([
            trajectoryHistoryApi.getLatest(userId),
            strategicPreferenceApi.getLatest(userId),
            compensationTargetApi.getLatest(userId),
        ]);

        const baseState = history?.trajectory_state || this.getDefaultState();
        const prefs = preferences || this.getDefaultPreferences();
        const comp = compensation || this.getDefaultCompensation();

        // Calculate momentum based on recent activity
        const momentum = await this.calculateMomentum(userId);

        // Calculate strategic positioning
        const strategicPositioning = this.calculateStrategicPositioning(baseState, prefs, comp);

        // Generate forecasted nodes
        const forecastedNodes = await this.generateForecastedNodes(
            userId,
            baseState,
            prefs,
            timeHorizonMonths,
        );

        // Calculate convergence probability
        const convergenceProbability = this.calculateConvergenceProbability(
            baseState,
            strategicPositioning,
            forecastedNodes,
        );

        return {
            current_role: baseState.current_role,
            target_roles: baseState.target_roles,
            career_stage: baseState.career_stage,
            momentum_score: momentum,
            convergence_probability: convergenceProbability,
            strategic_positioning: strategicPositioning,
            forecasted_nodes: forecastedNodes,
            time_horizon_months: timeHorizonMonths,
        };
    }

    /**
     * Calculate momentum score based on recent activity patterns
     */
    private async calculateMomentum(userId: string): Promise<number> {
        const recentMemories = await longitudinalMemoryApi.getRecent(userId, 30);
        const eventFrequency = await memoryAnalytics.getEventFrequency(userId);

        // Base momentum from activity frequency
        const activityScore = Math.min(recentMemories.length / 30, 1);

        // Positive momentum from applications and interviews
        const positiveEvents =
            (eventFrequency['job_applied'] || 0) * 0.3 +
            (eventFrequency['interview_scheduled'] || 0) * 0.5 +
            (eventFrequency['offer_received'] || 0) * 0.8;

        // Negative momentum from rejections
        const negativeEvents = (eventFrequency['offer_rejected'] || 0) * 0.2;

        // Normalize to 0-1
        const rawScore = activityScore * 0.4 + Math.min(positiveEvents / 10, 1) * 0.6 - Math.min(negativeEvents / 10, 0.3);
        return Math.max(0, Math.min(1, rawScore));
    }

    /**
     * Calculate strategic positioning metrics
     */
    private calculateStrategicPositioning(
        state: TrajectoryHistory['trajectory_state'],
        prefs: StrategicPreference,
        comp: CompensationTarget,
    ): TrajectoryForecast['strategic_positioning'] {
        // Market fit based on opportunity density and preferences
        const marketFit = this.calculateMarketFit(state, prefs);

        // Skill alignment based on career stage and target roles
        const skillAlignment = this.calculateSkillAlignment(state, prefs);

        // Opportunity density based on compensation targets and market conditions
        const opportunityDensity = this.calculateOpportunityDensity(comp, prefs);

        return {
            market_fit: marketFit,
            skill_alignment: skillAlignment,
            opportunity_density: opportunityDensity,
        };
    }

    private calculateMarketFit(state: TrajectoryHistory['trajectory_state'], prefs: StrategicPreference): number {
        // Higher fit if preferences align with current market conditions
        const industryAlignment = prefs.preferences.industry_focus.length > 0 ? 0.8 : 0.5;
        const roleAlignment = state.target_roles.length > 0 ? 0.7 : 0.4;
        return (industryAlignment + roleAlignment) / 2;
    }

    private calculateSkillAlignment(state: TrajectoryHistory['trajectory_state'], prefs: StrategicPreference): number {
        // Skill alignment improves with career progression
        const stageScores = { early: 0.4, mid: 0.6, senior: 0.8, executive: 0.9 };
        const baseScore = stageScores[state.career_stage];
        const learningBonus = prefs.preferences.learning_priority / 10 * 0.2;
        return Math.min(1, baseScore + learningBonus);
    }

    private calculateOpportunityDensity(comp: CompensationTarget, prefs: StrategicPreference): number {
        // Higher density for realistic compensation targets
        const targetComp = comp.target.total_compensation;
        const currentComp = comp.current.total_compensation;
        const growthRatio = targetComp / currentComp;

        // Reasonable growth (1.2x-2x) indicates good opportunity density
        if (growthRatio >= 1.2 && growthRatio <= 2) return 0.8;
        if (growthRatio > 2) return 0.5; // Overly ambitious
        if (growthRatio < 1.2) return 0.6; // Too conservative
        return 0.7;
    }

    /**
     * Generate forecasted trajectory nodes
     */
    private async generateForecastedNodes(
        userId: string,
        state: TrajectoryHistory['trajectory_state'],
        prefs: StrategicPreference,
        timeHorizonMonths: number,
    ): Promise<TrajectoryNode[]> {
        const nodes: TrajectoryNode[] = [];
        const now = new Date();

        // Generate opportunity nodes based on target roles
        for (const targetRole of state.target_roles) {
            const monthsToRole = this.estimateTimeToRole(state.career_stage, targetRole, prefs);
            if (monthsToRole <= timeHorizonMonths) {
                const targetDate = new Date(now);
                targetDate.setMonth(targetDate.getMonth() + monthsToRole);

                nodes.push({
                    id: `opp-${targetRole}-${monthsToRole}`,
                    type: 'opportunity',
                    title: `Transition to ${targetRole}`,
                    probability: this.calculateTransitionProbability(state, targetRole, prefs),
                    timing: {
                        optimal: targetDate.toISOString(),
                        window_start: new Date(targetDate.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString(),
                        window_end: new Date(targetDate.getTime() + 60 * 24 * 60 * 60 * 1000).toISOString(),
                        decay_rate: 0.05,
                    },
                    strategic_importance: this.calculateStrategicImportance(targetRole, prefs),
                });
            }
        }

        // Generate milestone nodes
        nodes.push(...this.generateMilestoneNodes(userId, state, timeHorizonMonths, now));

        // Sort by timing
        nodes.sort((a, b) => new Date(a.timing.optimal).getTime() - new Date(b.timing.optimal).getTime());

        return nodes;
    }

    private estimateTimeToRole(
        currentStage: TrajectoryHistory['trajectory_state']['career_stage'],
        targetRole: string,
        prefs: StrategicPreference,
    ): number {
        const stageMonths = { early: 24, mid: 36, senior: 48, executive: 60 };
        const baseMonths = stageMonths[currentStage];

        // Adjust based on career velocity
        const velocityMultiplier = {
            conservative: 1.3,
            moderate: 1.0,
            aggressive: 0.7,
        }[prefs.preferences.career_velocity];

        return Math.round(baseMonths * velocityMultiplier);
    }

    private calculateTransitionProbability(
        state: TrajectoryHistory['trajectory_state'],
        targetRole: string,
        prefs: StrategicPreference,
    ): number {
        // Base probability from momentum
        const baseProb = state.momentum_score;

        // Boost if role aligns with preferences
        const alignmentBoost = prefs.preferences.industry_focus.some(ind =>
            targetRole.toLowerCase().includes(ind.toLowerCase())
        ) ? 0.15 : 0;

        // Boost if learning priority is high
        const learningBoost = prefs.preferences.learning_priority / 10 * 0.1;

        return Math.min(1, baseProb + alignmentBoost + learningBoost);
    }

    private calculateStrategicImportance(targetRole: string, prefs: StrategicPreference): number {
        // Higher importance if role matches title progression
        const titleMatch = prefs.preferences.title_progression.some(title =>
            targetRole.toLowerCase().includes(title.toLowerCase())
        ) ? 0.9 : 0.6;

        // Adjust by compensation priority
        const compFactor = prefs.preferences.compensation_priority / 10 * 0.1;

        return Math.min(1, titleMatch + compFactor);
    }

    private generateMilestoneNodes(
        userId: string,
        state: TrajectoryHistory['trajectory_state'],
        timeHorizonMonths: number,
        now: Date,
    ): TrajectoryNode[] {
        const nodes: TrajectoryNode[] = [];

        // Generate compensation milestone
        const compMonths = 6;
        if (compMonths <= timeHorizonMonths) {
            const targetDate = new Date(now);
            targetDate.setMonth(targetDate.getMonth() + compMonths);

            nodes.push({
                id: 'milestone-compensation-review',
                type: 'milestone',
                title: 'Compensation Review',
                probability: 0.7,
                timing: {
                    optimal: targetDate.toISOString(),
                    window_start: new Date(targetDate.getTime() - 15 * 24 * 60 * 60 * 1000).toISOString(),
                    window_end: new Date(targetDate.getTime() + 15 * 24 * 60 * 60 * 1000).toISOString(),
                    decay_rate: 0.03,
                },
                strategic_importance: 0.8,
            });
        }

        return nodes;
    }

    /**
     * Calculate convergence probability - likelihood of reaching target state
     */
    private calculateConvergenceProbability(
        state: TrajectoryHistory['trajectory_state'],
        positioning: TrajectoryForecast['strategic_positioning'],
        nodes: TrajectoryNode[],
    ): number {
        // Base probability from strategic positioning
        const positioningScore = (
            positioning.market_fit +
            positioning.skill_alignment +
            positioning.opportunity_density
        ) / 3;

        // Boost from high-probability nodes
        const avgNodeProbability = nodes.length > 0
            ? nodes.reduce((sum, n) => sum + n.probability, 0) / nodes.length
            : 0.5;

        // Combine with momentum
        const momentumFactor = state.momentum_score * 0.3;
        const positioningFactor = positioningScore * 0.4;
        const nodeFactor = avgNodeProbability * 0.3;

        return Math.min(1, momentumFactor + positioningFactor + nodeFactor);
    }

    private getDefaultState(): TrajectoryHistory['trajectory_state'] {
        return {
            current_role: 'Unknown',
            target_roles: [],
            career_stage: 'mid',
            momentum_score: 0.5,
            convergence_probability: 0.5,
            strategic_positioning: {
                market_fit: 0.5,
                skill_alignment: 0.5,
                opportunity_density: 0.5,
            },
        };
    }

    private getDefaultPreferences(): StrategicPreference {
        return {
            user_id: '',
            timestamp: new Date().toISOString(),
            preferences: {
                career_velocity: 'moderate',
                risk_tolerance: 'medium',
                geographic_flexibility: 'regional',
                industry_focus: [],
                role_evolution: 'generalist',
                work_life_balance: 5,
                learning_priority: 5,
                compensation_priority: 5,
                title_progression: [],
            },
        };
    }

    private getDefaultCompensation(): CompensationTarget {
        return {
            user_id: '',
            timestamp: new Date().toISOString(),
            target: {
                base_salary: 100000,
                equity: '0.1%',
                bonus: 10000,
                benefits_value: 5000,
                total_compensation: 115000,
            },
            current: {
                base_salary: 80000,
                equity: '0%',
                bonus: 5000,
                benefits_value: 3000,
                total_compensation: 88000,
            },
            trajectory: {
                target_date: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),
                confidence: 0.5,
                required_moves: [],
            },
        };
    }
}

// ============================================================================
// Opportunity Momentum Calculations
// ============================================================================

export interface OpportunityMomentum {
    opportunity_id: string;
    momentum_score: number; // 0-1
    trend: 'rising' | 'stable' | 'declining';
    velocity: number; // change per week
    acceleration: number; // change in velocity
    saturation_window: {
        start: string;
        end: string;
        intensity: number; // 0-1
    };
    decay_probability: number; // 0-1
}

export class MomentumCalculator {
    /**
     * Calculate opportunity momentum based on historical weighting data
     */
    async calculateMomentum(userId: string, opportunityId: string): Promise<OpportunityMomentum> {
        const weightings = await opportunityWeightingApi.getByUserId(userId);
        const opportunityWeightings = weightings.filter(w => w.opportunity_id === opportunityId);

        if (opportunityWeightings.length === 0) {
            return this.getDefaultMomentum(opportunityId);
        }

        // Sort by timestamp
        const sorted = opportunityWeightings.sort(
            (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );

        const latest = sorted[sorted.length - 1];
        const previous = sorted.length > 1 ? sorted[sorted.length - 2] : latest;

        // Calculate velocity (change per week)
        const timeDiff = this.getTimeDiffWeeks(previous.timestamp, latest.timestamp);
        const momentumDiff = latest.momentum_score - previous.momentum_score;
        const velocity = timeDiff > 0 ? momentumDiff / timeDiff : 0;

        // Calculate acceleration (change in velocity)
        const acceleration = sorted.length > 2
            ? (velocity - (sorted[sorted.length - 3].momentum_score - sorted[sorted.length - 2].momentum_score) /
                this.getTimeDiffWeeks(sorted[sorted.length - 3].timestamp, sorted[sorted.length - 2].timestamp))
            : 0;

        // Determine trend
        const trend: 'rising' | 'stable' | 'declining' =
            velocity > 0.01 ? 'rising' : velocity < -0.01 ? 'declining' : 'stable';

        return {
            opportunity_id: opportunityId,
            momentum_score: latest.momentum_score,
            trend,
            velocity,
            acceleration,
            saturation_window: {
                start: latest.saturation_window.start || new Date().toISOString(),
                end: latest.saturation_window.end || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
                intensity: latest.saturation_window.intensity,
            },
            decay_probability: latest.decay_probability,
        };
    }

    private getTimeDiffWeeks(start: string, end: string): number {
        const diff = new Date(end).getTime() - new Date(start).getTime();
        return diff / (7 * 24 * 60 * 60 * 1000);
    }

    private getDefaultMomentum(opportunityId: string): OpportunityMomentum {
        return {
            opportunity_id: opportunityId,
            momentum_score: 0.5,
            trend: 'stable',
            velocity: 0,
            acceleration: 0,
            saturation_window: {
                start: new Date().toISOString(),
                end: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
                intensity: 0.5,
            },
            decay_probability: 0.1,
        };
    }
}

// ============================================================================
// Recruiter Signal Weighting
// ============================================================================

export interface RecruiterSignal {
    recruiter_id: string;
    recruiter_name: string;
    company: string;
    signal_strength: number; // 0-1
    response_rate: number; // 0-1
    communication_style: 'formal' | 'casual' | 'direct' | 'relationship-focused';
    last_interaction: string;
    interaction_count: number;
    positive_outcomes: number;
    strategic_value: number; // 0-1
}

export class RecruiterSignalWeighter {
    /**
     * Calculate recruiter signal strength based on interaction history
     */
    async calculateSignal(userId: string, recruiterId: string): Promise<RecruiterSignal> {
        const interactions = await recruiterInteractionApi.getByRecruiterId(recruiterId);
        const userInteractions = interactions.filter(i => i.user_id === userId);

        if (userInteractions.length === 0) {
            return this.getDefaultSignal(recruiterId);
        }

        const latest = userInteractions[userInteractions.length - 1];
        const positiveOutcomes = userInteractions.filter(i =>
            i.outcome === 'positive' || i.outcome === 'offer'
        ).length;

        // Calculate response rate
        const responseRate = positiveOutcomes / userInteractions.length;

        // Calculate signal strength based on outcomes and recency
        const recencyFactor = this.calculateRecencyFactor(latest.timestamp);
        const outcomeFactor = responseRate;
        const frequencyFactor = Math.min(userInteractions.length / 5, 1);

        const signalStrength = (recencyFactor * 0.3 + outcomeFactor * 0.5 + frequencyFactor * 0.2);

        // Calculate strategic value
        const strategicValue = this.calculateStrategicValue(latest, userInteractions);

        return {
            recruiter_id: recruiterId,
            recruiter_name: latest.recruiter_name,
            company: latest.company,
            signal_strength: signalStrength,
            response_rate: responseRate,
            communication_style: latest.communication_style || 'formal',
            last_interaction: latest.timestamp,
            interaction_count: userInteractions.length,
            positive_outcomes: positiveOutcomes,
            strategic_value: strategicValue,
        };
    }

    private calculateRecencyFactor(timestamp: string): number {
        const daysSince = (Date.now() - new Date(timestamp).getTime()) / (24 * 60 * 60 * 1000);
        return Math.max(0, 1 - daysSince / 90); // Decay over 90 days
    }

    private calculateStrategicValue(
        latest: RecruiterInteraction,
        interactions: RecruiterInteraction[],
    ): number {
        // Higher value for positive outcomes and recent interactions
        const positiveRatio = interactions.filter(i =>
            i.outcome === 'positive' || i.outcome === 'offer'
        ).length / interactions.length;

        const advancedStages = interactions.filter(i =>
            ['technical_interview', 'behavioral_interview', 'offer_negotiation'].includes(i.interaction_type)
        ).length / interactions.length;

        return (positiveRatio * 0.6 + advancedStages * 0.4);
    }

    private getDefaultSignal(recruiterId: string): RecruiterSignal {
        return {
            recruiter_id: recruiterId,
            recruiter_name: 'Unknown',
            company: 'Unknown',
            signal_strength: 0.3,
            response_rate: 0,
            communication_style: 'formal',
            last_interaction: new Date().toISOString(),
            interaction_count: 0,
            positive_outcomes: 0,
            strategic_value: 0.3,
        };
    }
}

// ============================================================================
// Convergence Detection
// ============================================================================

export interface ConvergencePoint {
    id: string;
    type: 'role_transition' | 'compensation_target' | 'strategic_alignment';
    title: string;
    probability: number; // 0-1
    time_to_convergence: number; // months
    required_actions: string[];
    blockers: string[];
    enablers: string[];
}

export class ConvergenceDetector {
    /**
     * Detect convergence points in the career trajectory
     */
    async detectConvergence(userId: string): Promise<ConvergencePoint[]> {
        const [history, preferences, compensation] = await Promise.all([
            trajectoryHistoryApi.getLatest(userId),
            strategicPreferenceApi.getLatest(userId),
            compensationTargetApi.getLatest(userId),
        ]);

        const convergences: ConvergencePoint[] = [];

        if (history && preferences) {
            // Detect role transition convergence
            for (const targetRole of history.trajectory_state.target_roles) {
                const convergence = this.detectRoleConvergence(history, preferences, targetRole);
                if (convergence) {
                    convergences.push(convergence);
                }
            }
        }

        if (compensation) {
            // Detect compensation target convergence
            const compConvergence = this.detectCompensationConvergence(compensation);
            if (compConvergence) {
                convergences.push(compConvergence);
            }
        }

        return convergences.sort((a, b) => b.probability - a.probability);
    }

    private detectRoleConvergence(
        history: TrajectoryHistory,
        preferences: StrategicPreference,
        targetRole: string,
    ): ConvergencePoint | null {
        const momentum = history.trajectory_state.momentum_score;
        const alignment = preferences.preferences.industry_focus.some(ind =>
            targetRole.toLowerCase().includes(ind.toLowerCase())
        ) ? 0.8 : 0.5;

        const probability = (momentum * 0.6 + alignment * 0.4);

        if (probability < 0.4) return null;

        return {
            id: `conv-role-${targetRole}`,
            type: 'role_transition',
            title: `Transition to ${targetRole}`,
            probability,
            time_to_convergence: this.estimateTimeToConvergence(probability),
            required_actions: ['Update resume', 'Network in target industry', 'Acquire missing skills'],
            blockers: ['Market conditions', 'Competition level'],
            enablers: ['Strong momentum', 'Industry alignment'],
        };
    }

    private detectCompensationConvergence(compensation: CompensationTarget): ConvergencePoint | null {
        const current = compensation.current.total_compensation;
        const target = compensation.target.total_compensation;
        const gap = target - current;
        const gapRatio = gap / current;

        const probability = Math.max(0, 1 - gapRatio / 2); // Higher probability for smaller gaps

        if (probability < 0.3) return null;

        return {
            id: 'conv-compensation',
            type: 'compensation_target',
            title: `Reach ${target} total compensation`,
            probability,
            time_to_convergence: this.estimateTimeToConvergence(probability),
            required_actions: ['Build case for value', 'Negotiation preparation', 'Market research'],
            blockers: ['Budget constraints', 'Company policies'],
            enablers: ['Strong performance', 'Market demand'],
        };
    }

    private estimateTimeToConvergence(probability: number): number {
        // Higher probability = faster convergence
        return Math.round(12 / probability);
    }
}

// ============================================================================
// Compensation Trajectory Estimation
// ============================================================================

export interface CompensationTrajectory {
    current: number;
    target: number;
    projected: number[];
    time_points: string[];
    confidence: number;
    growth_rate: number; // annual percentage
    required_moves: number;
}

export class CompensationEstimator {
    /**
     * Estimate compensation trajectory based on historical data and targets
     */
    async estimateTrajectory(userId: string, months = 24): Promise<CompensationTrajectory> {
        const [target, history] = await Promise.all([
            compensationTargetApi.getLatest(userId),
            compensationTargetApi.getByUserId(userId),
        ]);

        if (!target) {
            return this.getDefaultTrajectory();
        }

        const current = target.current.total_compensation;
        const targetComp = target.target.total_compensation;
        const confidence = target.trajectory.confidence;

        // Calculate growth rate needed
        const growthRate = this.calculateGrowthRate(current, targetComp, months);

        // Generate projected points
        const projected: number[] = [];
        const timePoints: string[] = [];
        const now = new Date();

        for (let i = 0; i <= months; i += 3) {
            const date = new Date(now);
            date.setMonth(date.getMonth() + i);
            timePoints.push(date.toISOString());

            const projectedValue = current * Math.pow(1 + growthRate / 100, i / 12);
            projected.push(projectedValue);
        }

        return {
            current,
            target: targetComp,
            projected,
            time_points: timePoints,
            confidence,
            growth_rate: growthRate * 100,
            required_moves: target.trajectory.required_moves.length,
        };
    }

    private calculateGrowthRate(current: number, target: number, months: number): number {
        const years = months / 12;
        const totalGrowth = (target - current) / current;
        return (Math.pow(1 + totalGrowth, 1 / years) - 1) * 100;
    }

    private getDefaultTrajectory(): CompensationTrajectory {
        const now = new Date();
        return {
            current: 80000,
            target: 100000,
            projected: [80000, 85000, 90000, 95000, 100000],
            time_points: [
                now.toISOString(),
                new Date(now.getTime() + 6 * 30 * 24 * 60 * 60 * 1000).toISOString(),
                new Date(now.getTime() + 12 * 30 * 24 * 60 * 60 * 1000).toISOString(),
                new Date(now.getTime() + 18 * 30 * 24 * 60 * 60 * 1000).toISOString(),
                new Date(now.getTime() + 24 * 30 * 24 * 60 * 60 * 1000).toISOString(),
            ],
            confidence: 0.5,
            growth_rate: 5,
            required_moves: 2,
        };
    }
}

// ============================================================================
// Strategic Positioning Logic
// ============================================================================

export interface StrategicPositioning {
    overall_score: number; // 0-1
    market_position: 'emerging' | 'established' | 'dominant' | 'declining';
    strengths: string[];
    weaknesses: string[];
    opportunities: string[];
    threats: string[];
    recommended_actions: string[];
}

export class StrategicPositioner {
    /**
     * Analyze strategic position and provide recommendations
     */
    async analyzePosition(userId: string): Promise<StrategicPositioning> {
        const [history, preferences, recruiterInteractions] = await Promise.all([
            trajectoryHistoryApi.getLatest(userId),
            strategicPreferenceApi.getLatest(userId),
            recruiterInteractionApi.getByUserId(userId),
        ]);

        const state = history?.trajectory_state || this.getDefaultState();
        const prefs = preferences || this.getDefaultPreferences();

        // Calculate overall score
        const overallScore = (
            state.momentum_score * 0.3 +
            state.strategic_positioning.market_fit * 0.25 +
            state.strategic_positioning.skill_alignment * 0.25 +
            state.strategic_positioning.opportunity_density * 0.2
        );

        // Determine market position
        const marketPosition = this.determineMarketPosition(overallScore, state.momentum_score);

        // Analyze SWOT
        const swot = this.analyzeSWOT(state, prefs, recruiterInteractions);

        // Generate recommendations
        const recommendations = this.generateRecommendations(state, prefs, swot);

        return {
            overall_score: overallScore,
            market_position: marketPosition,
            strengths: swot.strengths,
            weaknesses: swot.weaknesses,
            opportunities: swot.opportunities,
            threats: swot.threats,
            recommended_actions: recommendations,
        };
    }

    private determineMarketPosition(
        overallScore: number,
        momentum: number,
    ): 'emerging' | 'established' | 'dominant' | 'declining' {
        if (overallScore >= 0.8 && momentum >= 0.7) return 'dominant';
        if (overallScore >= 0.6) return 'established';
        if (momentum >= 0.6) return 'emerging';
        return 'declining';
    }

    private analyzeSWOT(
        state: TrajectoryHistory['trajectory_state'],
        prefs: StrategicPreference,
        recruiterInteractions: RecruiterInteraction[],
    ) {
        const strengths: string[] = [];
        const weaknesses: string[] = [];
        const opportunities: string[] = [];
        const threats: string[] = [];

        // Strengths
        if (state.momentum_score > 0.7) strengths.push('Strong career momentum');
        if (state.strategic_positioning.skill_alignment > 0.7) strengths.push('High skill alignment');
        if (prefs.preferences.learning_priority > 7) strengths.push('Strong learning orientation');

        // Weaknesses
        if (state.momentum_score < 0.4) weaknesses.push('Low career momentum');
        if (state.strategic_positioning.market_fit < 0.5) weaknesses.push('Limited market fit');
        if (recruiterInteractions.length < 5) weaknesses.push('Limited recruiter network');

        // Opportunities
        if (state.target_roles.length > 0) opportunities.push('Clear career trajectory');
        if (prefs.preferences.geographic_flexibility !== 'none') opportunities.push('Geographic flexibility');
        if (prefs.preferences.risk_tolerance === 'high') opportunities.push('Risk tolerance for growth');

        // Threats
        if (state.convergence_probability < 0.5) threats.push('Low convergence probability');
        if (prefs.preferences.work_life_balance > 7) threats.push('Potential work-life balance trade-offs');

        return { strengths, weaknesses, opportunities, threats };
    }

    private generateRecommendations(
        state: TrajectoryHistory['trajectory_state'],
        prefs: StrategicPreference,
        swot: ReturnType<typeof this.analyzeSWOT>,
    ): string[] {
        const recommendations: string[] = [];

        if (state.momentum_score < 0.5) {
            recommendations.push('Increase job application activity');
            recommendations.push('Expand networking efforts');
        }

        if (state.strategic_positioning.skill_alignment < 0.6) {
            recommendations.push('Focus on skill development');
            recommendations.push('Consider additional certifications');
        }

        if (prefs.preferences.learning_priority > 7) {
            recommendations.push('Leverage learning orientation for skill acquisition');
        }

        if (swot.weaknesses.includes('Limited recruiter network')) {
            recommendations.push('Build recruiter relationships through outreach');
        }

        return recommendations;
    }

    private getDefaultState(): TrajectoryHistory['trajectory_state'] {
        return {
            current_role: 'Unknown',
            target_roles: [],
            career_stage: 'mid',
            momentum_score: 0.5,
            convergence_probability: 0.5,
            strategic_positioning: {
                market_fit: 0.5,
                skill_alignment: 0.5,
                opportunity_density: 0.5,
            },
        };
    }

    private getDefaultPreferences(): StrategicPreference {
        return {
            user_id: '',
            timestamp: new Date().toISOString(),
            preferences: {
                career_velocity: 'moderate',
                risk_tolerance: 'medium',
                geographic_flexibility: 'regional',
                industry_focus: [],
                role_evolution: 'generalist',
                work_life_balance: 5,
                learning_priority: 5,
                compensation_priority: 5,
                title_progression: [],
            },
        };
    }
}
