export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type Decision = 'ALLOW' | 'WARN' | 'BLOCK' | 'ESCALATE';

export function getRiskHex(level: RiskLevel | string): string {
  const map: Record<string, string> = {
    critical: 'var(--critical)',
    high: 'var(--high)',
    medium: 'var(--medium)',
    low: 'var(--low)'
  };
  return map[level] ?? 'var(--text-secondary)';
}

export function getDecisionClass(decision: Decision | string): string {
  const map: Record<string, string> = {
    BLOCK: 'decision-block',
    ESCALATE: 'decision-escalate',
    WARN: 'decision-warn',
    ALLOW: 'decision-allow'
  };
  return map[decision] ?? '';
}

export function getThreatHex(score: number): string {
  if (score >= 0.85) return 'var(--critical)';
  if (score >= 0.70) return 'var(--high)';
  if (score >= 0.55) return 'var(--medium)';
  return 'var(--low)';
}
