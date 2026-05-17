/**
 * Temporal Orchestration Engine
 * Handles optimal move timing, recruiter saturation windows, compensation leverage,
 * strategic silence periods, market-entry timing, and opportunity decay probability.
 */

import {
    compensationTargetApi,
    longitudinalMemoryApi,
    recruiterInteractionApi,
    strategicPreferenceApi
} from '@/lib/memory';
import type {
    CompensationTarget,
    RecruiterInteraction,
    StrategicPreference
} from '@/lib/schemas';

// ============================================================================
// Optimal Move Timing Models
// ============================================================================

export interface OptimalMoveTiming {
    move_type: 'job_change' | 'promotion' | 'negotiation' | 'networking';
    optimal_date: string;
    window_start: string;
    window_end: string;
    confidence: number; // 0-1
    reasoning: string[];
    risk_factors: string[];
    enablers: string[];
}

export class MoveTimingOptimizer {
    /**
     * Calculate optimal timing for various career moves
     */
    async calculateOptimalTiming(userId: string, moveType: OptimalMoveTiming['move_type']): Promise<OptimalMoveTiming> {
        const [preferences, compensation, recentActivity] = await Promise.all([
            strategicPreferenceApi.getLatest(userId),
            compensationTargetApi.getLatest(userId),
            longitudinalMemoryApi.getRecent(userId, 90),
        ]);

        const prefs = preferences || this.getDefaultPreferences();
        const comp = compensation || this.getDefaultCompensation();

        const baseTiming = this.calculateBaseTiming(moveType, prefs, comp, recentActivity);
        const window = this.calculateTimingWindow(baseTiming, moveType, prefs);
        const confidence = this.calculateConfidence(baseTiming, recentActivity, prefs);
        const analysis = this.analyzeFactors(baseTiming, recentActivity, prefs, comp);

        return {
            move_type: moveType,
            optimal_date: baseTiming.toISOString(),
            window_start: window.start,
            window_end: window.end,
            confidence,
            reasoning: analysis.reasoning,
            risk_factors: analysis.risk_factors,
            enablers: analysis.enablers,
        };
    }

    private calculateBaseTiming(
        moveType: OptimalMoveTiming['move_type'],
        prefs: StrategicPreference,
        comp: CompensationTarget,
        recentActivity: any[],
    ): Date {
        const now = new Date();
        const careerVelocity = this.getCareerVelocityMultiplier(prefs);

        switch (moveType) {
            case 'job_change':
                // Job changes optimal every 18-24 months, adjusted by velocity
                const jobChangeMonths = 18 / careerVelocity;
                return new Date(now.getTime() + jobChangeMonths * 30 * 24 * 60 * 60 * 1000);

            case 'promotion':
                // Promotions optimal every 12-18 months
                const promotionMonths = 15 / careerVelocity;
                return new Date(now.getTime() + promotionMonths * 30 * 24 * 60 * 60 * 1000);

            case 'negotiation':
                // Negotiations optimal near performance reviews or offer stages
                const negotiationMonths = 3;
                return new Date(now.getTime() + negotiationMonths * 30 * 24 * 60 * 60 * 1000);

            case 'networking':
                // Networking optimal continuously, with peaks
                const networkingDays = 14;
                return new Date(now.getTime() + networkingDays * 24 * 60 * 60 * 1000);

            default:
                return new Date(now.getTime() + 90 * 24 * 60 * 60 * 1000);
        }
    }

    private calculateTimingWindow(
        baseDate: Date,
        moveType: OptimalMoveTiming['move_type'],
        prefs: StrategicPreference,
    ): { start: string; end: string } {
        const windowDays = {
            job_change: 60,
            promotion: 45,
            negotiation: 30,
            networking: 14,
        }[moveType];

        const riskTolerance = this.getRiskToleranceMultiplier(prefs);
        const adjustedWindow = Math.round(windowDays * riskTolerance);

        return {
            start: new Date(baseDate.getTime() - adjustedWindow * 24 * 60 * 60 * 1000).toISOString(),
            end: new Date(baseDate.getTime() + adjustedWindow * 24 * 60 * 60 * 1000).toISOString(),
        };
    }

    private calculateConfidence(baseDate: Date, recentActivity: any[], prefs: StrategicPreference): number {
        // Higher confidence with consistent activity
        const activityScore = Math.min(recentActivity.length / 30, 1);
        const learningBonus = prefs.preferences.learning_priority / 10 * 0.1;
        const riskAdjustment = prefs.preferences.risk_tolerance === 'high' ? 0.1 : 0;

        return Math.min(1, activityScore * 0.7 + learningBonus + riskAdjustment);
    }

    private analyzeFactors(
        baseDate: Date,
        recentActivity: any[],
        prefs: StrategicPreference,
        comp: CompensationTarget,
    ): { reasoning: string[]; risk_factors: string[]; enablers: string[] } {
        const reasoning: string[] = [];
        const risk_factors: string[] = [];
        const enablers: string[] = [];

        // Analyze activity patterns
        const recent_applications = recentActivity.filter(a => a.event_type === 'job_applied').length;
        if (recent_applications > 10) {
            reasoning.push('High application activity indicates market engagement');
            enablers.push('Strong market presence');
        } else if (recent_applications < 3) {
            risk_factors.push('Low application activity may indicate market disengagement');
        }

        // Analyze compensation trajectory
        const comp_gap = comp.target.total_compensation - comp.current.total_compensation;
        if (comp_gap > 20000) {
            reasoning.push('Significant compensation gap provides motivation for change');
            risk_factors.push('Large compensation gap may be challenging to bridge');
        }

        // Analyze preferences
        if (prefs.preferences.career_velocity === 'aggressive') {
            reasoning.push('Aggressive career velocity supports proactive timing');
            enablers.push('High career ambition');
        }

        return { reasoning, risk_factors, enablers };
    }

    private getCareerVelocityMultiplier(prefs: StrategicPreference): number {
        return {
            conservative: 1.3,
            moderate: 1.0,
            aggressive: 0.7,
        }[prefs.preferences.career_velocity];
    }

    private getRiskToleranceMultiplier(prefs: StrategicPreference): number {
        return {
            low: 0.7,
            medium: 1.0,
            high: 1.3,
        }[prefs.preferences.risk_tolerance];
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
// Recruiter Saturation Window Detection
// ============================================================================

export interface SaturationWindow {
    recruiter_id: string;
    recruiter_name: string;
    company: string;
    saturation_level: number; // 0-1
    window_start: string;
    window_end: string;
    recommended_action: 'avoid_contact' | 'proceed_cautiously' | 'proceed_normally' | 'prioritize_contact';
    reasoning: string;
}

export class SaturationDetector {
    /**
     * Detect recruiter saturation windows based on interaction patterns
     */
    async detectSaturation(userId: string, recruiterId: string): Promise<SaturationWindow> {
        const interactions = await recruiterInteractionApi.getByRecruiterId(recruiterId);
        const userInteractions = interactions.filter(i => i.user_id === userId);

        if (userInteractions.length === 0) {
            return this.getDefaultSaturation(recruiterId);
        }

        const latest = userInteractions[userInteractions.length - 1];
        const saturationLevel = this.calculateSaturationLevel(userInteractions);
        const window = this.calculateSaturationWindow(userInteractions, saturationLevel);
        const recommendation = this.getRecommendation(saturationLevel, latest);
        const reasoning = this.generateReasoning(saturationLevel, userInteractions, latest);

        return {
            recruiter_id: recruiterId,
            recruiter_name: latest.recruiter_name,
            company: latest.company,
            saturation_level: saturationLevel,
            window_start: window.start,
            window_end: window.end,
            recommended_action: recommendation,
            reasoning,
        };
    }

    private calculateSaturationLevel(interactions: RecruiterInteraction[]): number {
        // Higher saturation with more frequent recent interactions
        const now = new Date();
        const recentInteractions = interactions.filter(i => {
            const daysSince = (now.getTime() - new Date(i.timestamp).getTime()) / (24 * 60 * 60 * 1000);
            return daysSince <= 30;
        });

        const baseLevel = Math.min(recentInteractions.length / 5, 1);

        // Adjust based on outcomes - negative outcomes increase saturation
        const negativeOutcomes = interactions.filter(i =>
            ['negative', 'rejected'].includes(i.outcome)
        ).length;
        const negativeAdjustment = (negativeOutcomes / interactions.length) * 0.3;

        return Math.min(1, baseLevel + negativeAdjustment);
    }

    private calculateSaturationWindow(
        interactions: RecruiterInteraction[],
        saturationLevel: number,
    ): { start: string; end: string } {
        const now = new Date();
        const windowDays = Math.round(saturationLevel * 30); // Up to 30 days based on saturation

        return {
            start: now.toISOString(),
            end: new Date(now.getTime() + windowDays * 24 * 60 * 60 * 1000).toISOString(),
        };
    }

    private getRecommendation(
        saturationLevel: number,
        latest: RecruiterInteraction,
    ): SaturationWindow['recommended_action'] {
        if (saturationLevel > 0.8) return 'avoid_contact';
        if (saturationLevel > 0.6) return 'proceed_cautiously';
        if (latest.outcome === 'positive' || latest.outcome === 'offer') return 'prioritize_contact';
        return 'proceed_normally';
    }

    private generateReasoning(
        saturationLevel: number,
        interactions: RecruiterInteraction[],
        latest: RecruiterInteraction,
    ): string {
        const recentCount = interactions.filter(i => {
            const daysSince = (Date.now() - new Date(i.timestamp).getTime()) / (24 * 60 * 60 * 1000);
            return daysSince <= 30;
        }).length;

        if (saturationLevel > 0.8) {
            return `High saturation detected: ${recentCount} interactions in past 30 days. Recommend avoiding contact to prevent overwhelming the recruiter.`;
        } else if (saturationLevel > 0.6) {
            return `Moderate saturation: ${recentCount} interactions in past 30 days. Proceed cautiously with spaced-out communication.`;
        } else if (latest.outcome === 'positive') {
            return `Low saturation with positive recent outcome. Good time to prioritize contact and advance the relationship.`;
        } else {
            return `Low saturation level. Normal communication patterns are appropriate.`;
        }
    }

    private getDefaultSaturation(recruiterId: string): SaturationWindow {
        return {
            recruiter_id: recruiterId,
            recruiter_name: 'Unknown',
            company: 'Unknown',
            saturation_level: 0.2,
            window_start: new Date().toISOString(),
            window_end: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
            recommended_action: 'proceed_normally',
            reasoning: 'No prior interaction history. Normal communication patterns are appropriate.',
        };
    }
}

// ============================================================================
// Compensation Leverage Timing
// ============================================================================

export interface CompensationLeverage {
    leverage_score: number; // 0-1
    optimal_timing: string;
    leverage_points: string[];
    market_position: 'strong' | 'moderate' | 'weak';
    recommended_strategy: string;
    risk_assessment: string;
}

export class CompensationLeverageCalculator {
    /**
     * Calculate optimal timing for compensation negotiations
     */
    async calculateLeverage(userId: string): Promise<CompensationLeverage> {
        const [compensation, recentActivity, recruiterInteractions] = await Promise.all([
            compensationTargetApi.getLatest(userId),
            longitudinalMemoryApi.getRecent(userId, 90),
            recruiterInteractionApi.getByUserId(userId),
        ]);

        const comp = compensation || this.getDefaultCompensation();
        const leverageScore = this.calculateLeverageScore(comp, recentActivity, recruiterInteractions);
        const optimalTiming = this.calculateOptimalTiming(recentActivity, recruiterInteractions);
        const leveragePoints = this.identifyLeveragePoints(comp, recentActivity, recruiterInteractions);
        const marketPosition = this.assessMarketPosition(leverageScore, recruiterInteractions);
        const strategy = this.recommendStrategy(marketPosition, leveragePoints);
        const risk = this.assessRisk(leverageScore, recentActivity);

        return {
            leverage_score: leverageScore,
            optimal_timing: optimalTiming,
            leverage_points: leveragePoints,
            market_position: marketPosition,
            recommended_strategy: strategy,
            risk_assessment: risk,
        };
    }

    private calculateLeverageScore(
        comp: CompensationTarget,
        recentActivity: any[],
        recruiterInteractions: RecruiterInteraction[],
    ): number {
        // Base score from current vs target compensation
        const compRatio = comp.current.total_compensation / comp.target.total_compensation;
        const compScore = compRatio < 0.8 ? 0.9 : compRatio < 0.9 ? 0.7 : 0.5;

        // Activity score - consistent application activity
        const recentApplications = recentActivity.filter(a => a.event_type === 'job_applied').length;
        const activityScore = Math.min(recentApplications / 20, 1) * 0.3;

        // Recruiter score - positive interactions indicate market demand
        const positiveInteractions = recruiterInteractions.filter(i =>
            i.outcome === 'positive' || i.outcome === 'offer'
        ).length;
        const recruiterScore = Math.min(positiveInteractions / 5, 1) * 0.2;

        return Math.min(1, compScore + activityScore + recruiterScore);
    }

    private calculateOptimalTiming(recentActivity: any[], recruiterInteractions: RecruiterInteraction[]): string {
        // Optimal timing after positive interactions or performance reviews
        const positiveInteractions = recruiterInteractions.filter(i =>
            i.outcome === 'positive'
        );

        if (positiveInteractions.length > 0) {
            const latestPositive = positiveInteractions[positiveInteractions.length - 1];
            const daysSince = (Date.now() - new Date(latestPositive.timestamp).getTime()) / (24 * 60 * 60 * 1000);

            if (daysSince <= 14) {
                return 'Immediate - capitalize on recent positive outcome';
            } else if (daysSince <= 30) {
                return 'Within 2 weeks - leverage still fresh';
            }
        }

        // Check for recent interviews (indicates market interest)
        const recentInterviews = recentActivity.filter(a => a.event_type === 'interview_scheduled');
        if (recentInterviews.length > 0) {
            return 'After securing competing offers - use as leverage';
        }

        return 'During performance review cycle or after significant achievement';
    }

    private identifyLeveragePoints(
        comp: CompensationTarget,
        recentActivity: any[],
        recruiterInteractions: RecruiterInteraction[],
    ): string[] {
        const points: string[] = [];

        // Compensation gap
        const compGap = comp.target.total_compensation - comp.current.total_compensation;
        if (compGap > 20000) {
            points.push(`$${(compGap / 1000).toFixed(0)}k below market target`);
        }

        // Market demand from recruiters
        const activeRecruiters = recruiterInteractions.filter(i => i.outcome === 'positive').length;
        if (activeRecruiters >= 3) {
            points.push(`${activeRecruiters} active recruiter relationships indicate market demand`);
        }

        // Recent achievements
        const recentOffers = recentActivity.filter(a => a.event_type === 'offer_received').length;
        if (recentOffers > 0) {
            points.push(`${recentOffers} recent offer(s) provide competitive leverage`);
        }

        return points;
    }

    private assessMarketPosition(leverageScore: number, recruiterInteractions: RecruiterInteraction[]): CompensationLeverage['market_position'] {
        if (leverageScore >= 0.7) return 'strong';
        if (leverageScore >= 0.4) return 'moderate';
        return 'weak';
    }

    private recommendStrategy(marketPosition: CompensationLeverage['market_position'], leveragePoints: string[]): string {
        switch (marketPosition) {
            case 'strong':
                return 'Aggressive negotiation - use competing offers and market demand to secure top compensation';
            case 'moderate':
                return 'Balanced approach - highlight value proposition while being prepared to compromise';
            case 'weak':
                return 'Conservative strategy - focus on securing role with growth potential, negotiate compensation later';
        }
    }

    private assessRisk(leverageScore: number, recentActivity: any[]): string {
        if (leverageScore >= 0.7) return 'Low risk - strong market position supports confident negotiation';
        if (leverageScore >= 0.4) return 'Moderate risk - careful timing and preparation required';
        return 'High risk - consider building leverage before negotiation';
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
// Strategic Silence Period Modeling
// ============================================================================

export interface SilencePeriod {
    period_type: 'post_application' | 'post_interview' | 'post_negotiation' | 'post_rejection';
    recommended_duration_days: number;
    start_date: string;
    end_date: string;
    reasoning: string;
    recommended_actions: string[];
}

export class SilencePeriodModeler {
    /**
     * Model optimal silence periods after various interactions
     */
    async modelSilencePeriod(
        userId: string,
        periodType: SilencePeriod['period_type'],
        lastInteractionDate?: string,
    ): Promise<SilencePeriod> {
        const [preferences, recruiterInteractions] = await Promise.all([
            strategicPreferenceApi.getLatest(userId),
            recruiterInteractionApi.getByUserId(userId),
        ]);

        const prefs = preferences || this.getDefaultPreferences();
        const baseDuration = this.getBaseDuration(periodType);
        const adjustedDuration = this.adjustDurationByPreferences(baseDuration, prefs, recruiterInteractions);
        const startDate = lastInteractionDate ? new Date(lastInteractionDate) : new Date();
        const endDate = new Date(startDate.getTime() + adjustedDuration * 24 * 60 * 60 * 1000);

        return {
            period_type: periodType,
            recommended_duration_days: adjustedDuration,
            start_date: startDate.toISOString(),
            end_date: endDate.toISOString(),
            reasoning: this.generateReasoning(periodType, adjustedDuration, prefs),
            recommended_actions: this.getRecommendedActions(periodType, adjustedDuration),
        };
    }

    private getBaseDuration(periodType: SilencePeriod['period_type']): number {
        return {
            post_application: 7,
            post_interview: 14,
            post_negotiation: 21,
            post_rejection: 30,
        }[periodType];
    }

    private adjustDurationByPreferences(
        baseDuration: number,
        prefs: StrategicPreference,
        recruiterInteractions: RecruiterInteraction[],
    ): number {
        // Adjust based on career velocity
        const velocityMultiplier = {
            conservative: 1.5,
            moderate: 1.0,
            aggressive: 0.7,
        }[prefs.preferences.career_velocity];

        // Adjust based on recruiter relationship strength
        const positiveRatio = recruiterInteractions.length > 0
            ? recruiterInteractions.filter(i => i.outcome === 'positive').length / recruiterInteractions.length
            : 0;
        const relationshipMultiplier = positiveRatio > 0.5 ? 0.8 : 1.2;

        return Math.round(baseDuration * velocityMultiplier * relationshipMultiplier);
    }

    private generateReasoning(periodType: SilencePeriod['period_type'], duration: number, prefs: StrategicPreference): string {
        const velocityText = {
            conservative: 'extended',
            moderate: 'standard',
            aggressive: 'shortened',
        }[prefs.preferences.career_velocity];

        return `Based on ${velocityText} career velocity, recommend ${duration} days of ${periodType.replace('_', ' ')} to allow for natural process flow while maintaining momentum.`;
    }

    private getRecommendedActions(periodType: SilencePeriod['period_type'], duration: number): string[] {
        const actions: string[] = ['Continue networking and research opportunities'];

        switch (periodType) {
            case 'post_application':
                actions.push('Prepare for potential interview questions');
                actions.push('Research company culture and recent news');
                break;
            case 'post_interview':
                actions.push('Send thank-you note immediately after silence period');
                actions.push('Reflect on interview performance and areas for improvement');
                break;
            case 'post_negotiation':
                actions.push('Prepare for onboarding if accepted');
                actions.push('Keep pipeline warm with other opportunities');
                break;
            case 'post_rejection':
                actions.push('Request feedback if appropriate');
                actions.push('Analyze rejection patterns and adjust strategy');
                break;
        }

        return actions;
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

// ============================================================================
// Market-Entry Timing Logic
// ============================================================================

export interface MarketEntryTiming {
    optimal_entry_point: string;
    market_condition: 'hot' | 'warm' | 'cool' | 'cold';
    competition_level: 'low' | 'moderate' | 'high';
    recommended_strategy: string;
    timing_factors: string[];
}

export class MarketEntryTimer {
    /**
     * Calculate optimal market entry timing based on seasonal and cyclical patterns
     */
    async calculateEntryTiming(userId: string, targetIndustry?: string): Promise<MarketEntryTiming> {
        const now = new Date();
        const month = now.getMonth();
        const quarter = Math.floor(month / 3);

        const marketCondition = this.assessMarketCondition(month, quarter);
        const competitionLevel = this.assessCompetitionLevel(month, quarter);
        const optimalEntry = this.calculateOptimalEntry(month, quarter, marketCondition);
        const strategy = this.recommendEntryStrategy(marketCondition, competitionLevel);
        const factors = this.identifyTimingFactors(month, quarter, targetIndustry);

        return {
            optimal_entry_point: optimalEntry,
            market_condition: marketCondition,
            competition_level: competitionLevel,
            recommended_strategy: strategy,
            timing_factors: factors,
        };
    }

    private assessMarketCondition(month: number, quarter: number): MarketEntryTiming['market_condition'] {
        // Q1 (Jan-Mar): Post-holiday hiring surge - hot
        // Q2 (Apr-Jun): Moderate hiring - warm
        // Q3 (Jul-Sep): Summer slowdown - cool
        // Q4 (Oct-Dec): Year-end push - warm/cold depending on industry

        if (quarter === 0) return 'hot';
        if (quarter === 1) return 'warm';
        if (quarter === 2) return 'cool';
        if (month >= 10) return 'warm';
        return 'cold';
    }

    private assessCompetitionLevel(month: number, quarter: number): MarketEntryTiming['competition_level'] {
        // Competition inversely related to market condition
        const condition = this.assessMarketCondition(month, quarter);

        if (condition === 'hot') return 'high';
        if (condition === 'warm') return 'moderate';
        if (condition === 'cool') return 'low';
        return 'low';
    }

    private calculateOptimalEntry(month: number, quarter: number, condition: MarketEntryTiming['market_condition']): string {
        const now = new Date();

        // If currently in hot market, enter now
        if (condition === 'hot') {
            return 'Immediate - current market conditions favorable';
        }

        // If in warm market, enter within 2 weeks
        if (condition === 'warm') {
            const targetDate = new Date(now.getTime() + 14 * 24 * 60 * 60 * 1000);
            return targetDate.toISOString().split('T')[0];
        }

        // If in cool market, wait for Q1
        if (condition === 'cool') {
            const nextYear = now.getFullYear() + (month >= 9 ? 1 : 0);
            return `${nextYear}-01-15`;
        }

        // If cold market, wait for early Q1
        const nextYear = now.getFullYear() + 1;
        return `${nextYear}-02-01`;
    }

    private recommendEntryStrategy(
        condition: MarketEntryTiming['market_condition'],
        competition: MarketEntryTiming['competition_level'],
    ): string {
        if (condition === 'hot' && competition === 'high') {
            return 'Aggressive entry - move quickly but differentiate strongly to stand out';
        }
        if (condition === 'hot' && competition === 'moderate') {
            return 'Active entry - leverage favorable conditions with strong value proposition';
        }
        if (condition === 'warm') {
            return 'Measured entry - maintain consistent activity while building relationships';
        }
        if (condition === 'cool' || condition === 'cold') {
            return 'Strategic preparation - focus on skill development and networking during slow period';
        }
        return 'Standard entry approach';
    }

    private identifyTimingFactors(month: number, quarter: number, targetIndustry?: string): string[] {
        const factors: string[] = [];

        if (quarter === 0) factors.push('Q1 hiring surge - budgets refreshed, new headcount approved');
        if (quarter === 1) factors.push('Q2 steady hiring - mid-year planning adjustments');
        if (quarter === 2) factors.push('Q3 summer slowdown - reduced hiring activity, longer timelines');
        if (quarter === 3) {
            if (month >= 10) factors.push('Year-end hiring push - use remaining budget');
            else factors.push('Year-end slowdown - hiring freezes common');
        }

        if (targetIndustry) {
            factors.push(`Industry-specific seasonal patterns for ${targetIndustry}`);
        }

        return factors;
    }
}

// ============================================================================
// Opportunity Decay Probability
// ============================================================================

export interface DecayProbability {
    opportunity_id: string;
    current_decay_probability: number; // 0-1
    decay_rate_per_day: number;
    estimated_expiry_date: string;
    urgency_level: 'low' | 'moderate' | 'high' | 'critical';
    recommended_action: string;
}

export class DecayProbabilityCalculator {
    /**
     * Calculate opportunity decay probability based on age and market factors
    */
    async calculateDecay(
        opportunityId: string,
        postingDate: string,
        marketCondition: MarketEntryTiming['market_condition'] = 'warm',
    ): Promise<DecayProbability> {
        const now = new Date();
        const posted = new Date(postingDate);
        const daysSincePosting = (now.getTime() - posted.getTime()) / (24 * 60 * 60 * 1000);

        const baseDecayRate = this.getBaseDecayRate(marketCondition);
        const currentDecayProbability = this.calculateCurrentDecay(daysSincePosting, baseDecayRate);
        const estimatedExpiry = this.estimateExpiry(daysSincePosting, baseDecayRate);
        const urgency = this.assessUrgency(currentDecayProbability, daysSincePosting);
        const action = this.recommendAction(urgency, daysSincePosting);

        return {
            opportunity_id: opportunityId,
            current_decay_probability: currentDecayProbability,
            decay_rate_per_day: baseDecayRate,
            estimated_expiry_date: estimatedExpiry,
            urgency_level: urgency,
            recommended_action: action,
        };
    }

    private getBaseDecayRate(marketCondition: MarketEntryTiming['market_condition']): number {
        // Decay rate varies by market condition
        return {
            hot: 0.02, // 2% per day in hot market (faster decay due to high competition)
            warm: 0.015, // 1.5% per day in warm market
            cool: 0.01, // 1% per day in cool market
            cold: 0.005, // 0.5% per day in cold market
        }[marketCondition];
    }

    private calculateCurrentDecay(daysSince: number, decayRate: number): number {
        // Exponential decay model
        return Math.min(1, 1 - Math.exp(-decayRate * daysSince));
    }

    private estimateExpiry(daysSince: number, decayRate: number): string {
        const now = new Date();
        // Estimate when decay reaches 80%
        const daysTo80Percent = Math.log(0.2) / -decayRate;
        const remainingDays = Math.max(0, daysTo80Percent - daysSince);
        const expiryDate = new Date(now.getTime() + remainingDays * 24 * 60 * 60 * 1000);
        return expiryDate.toISOString();
    }

    private assessUrgency(decayProbability: number, daysSince: number): DecayProbability['urgency_level'] {
        if (decayProbability >= 0.8 || daysSince >= 30) return 'critical';
        if (decayProbability >= 0.6 || daysSince >= 21) return 'high';
        if (decayProbability >= 0.4 || daysSince >= 14) return 'moderate';
        return 'low';
    }

    private recommendAction(urgency: DecayProbability['urgency_level'], daysSince: number): string {
        switch (urgency) {
            case 'critical':
                return 'Apply immediately - opportunity near expiry, high risk of missing out';
            case 'high':
                return 'Apply within 24-48 hours - significant decay, window closing';
            case 'moderate':
                return 'Apply within 3-5 days - moderate urgency, still viable';
            case 'low':
                return 'Apply within 7-10 days - low urgency, good window remains';
        }
    }
}
