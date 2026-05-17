export interface CommandSuggestion {
  id: string;
  command: string;
  description: string;
  category: 'trajectory' | 'signals' | 'analysis' | 'optimization';
}

export const commandSuggestions: CommandSuggestion[] = [
  {
    id: '1',
    command: 'Simulate compensation trajectory for Series C CTO roles',
    description: 'Analyze compensation patterns for executive roles at Series C companies',
    category: 'trajectory',
  },
  {
    id: '2',
    command: 'Map recruiter clusters in East London fintech hub',
    description: 'Identify active recruiter networks in specific geographic clusters',
    category: 'signals',
  },
  {
    id: '3',
    command: 'Analyze my profile alignment with founder-track opportunities',
    description: 'Evaluate profile fit against successful founder trajectory patterns',
    category: 'analysis',
  },
  {
    id: '4',
    command: 'Optimize my CV for Series B engineering leadership roles',
    description: 'Refine CV content based on role-specific success patterns',
    category: 'optimization',
  },
  {
    id: '5',
    command: 'Forecast career velocity over 24-month horizon',
    description: 'Generate probability-weighted trajectory forecast',
    category: 'trajectory',
  },
  {
    id: '6',
    command: 'Identify high-momentum opportunities in London fintech',
    description: 'Surface opportunities with strong recruiter and market momentum',
    category: 'signals',
  },
];

export const operationalCommands = [
  'STRATEGIC VECTOR',
  'QUERY MEMORY LAYER',
  'LOCK SEQUENCE',
  'EXPORT TRAJECTORY',
  'ANALYZE PATTERNS',
];
