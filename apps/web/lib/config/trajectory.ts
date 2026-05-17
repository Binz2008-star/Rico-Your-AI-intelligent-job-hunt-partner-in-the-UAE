export interface TrajectoryNode {
  id: string;
  title: string;
  description: string;
  probability: number;
  timeline: string;
  status: 'current' | 'upcoming' | 'completed';
  tags?: string[];
}

export const defaultTrajectory: TrajectoryNode[] = [
  {
    id: '1',
    title: 'Series C CTO Transition',
    description: 'Optimizing for scale-up operational density. Focus on organizational architecture before equity liquidity event.',
    probability: 0.94,
    timeline: 'Q3 2024',
    status: 'current',
    tags: ['LOW FRICTION', 'HIGH IMPACT'],
  },
  {
    id: '2',
    title: 'Stealth Phase Initiation',
    description: 'Leveraging secondary market capital for initial talent capture. Constructing core architectural layers.',
    probability: 0.82,
    timeline: 'Q1 2025',
    status: 'upcoming',
    tags: ['HIGH IMPACT', 'STRATEGIC'],
  },
  {
    id: '3',
    title: 'Early Stage Founder',
    description: 'Final state transition into venture-backed leadership. Trajectory lock achieved via historical pattern matching.',
    probability: 0.76,
    timeline: 'Q4 2025',
    status: 'upcoming',
    tags: ['LONG-TERM', 'STRATEGIC POSITION'],
  },
];

export interface OpportunitySignal {
  id: string;
  company: string;
  role: string;
  matchScore: number;
  momentum: 'high' | 'medium' | 'low';
  location: string;
  timestamp: string;
  sector?: string;
  stage?: string;
}

export const defaultSignals: OpportunitySignal[] = [
  {
    id: '1',
    company: 'TechCorp London',
    role: 'Senior Engineering Lead',
    matchScore: 94,
    momentum: 'high',
    location: 'London, UK',
    timestamp: new Date().toISOString(),
    sector: 'Fintech',
    stage: 'Series B',
  },
  {
    id: '2',
    company: 'FinanceHub',
    role: 'Tech Lead',
    matchScore: 87,
    momentum: 'high',
    location: 'London, UK',
    timestamp: new Date().toISOString(),
    sector: 'Fintech',
    stage: 'Series C',
  },
  {
    id: '3',
    company: 'DataFlow',
    role: 'Engineering Manager',
    matchScore: 82,
    momentum: 'medium',
    location: 'Berlin, DE',
    timestamp: new Date().toISOString(),
    sector: 'Data Infrastructure',
    stage: 'Series A',
  },
];
