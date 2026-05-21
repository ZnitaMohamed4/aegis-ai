export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type Decision = 'ALLOW' | 'WARN' | 'BLOCK' | 'ESCALATE';

export function getRiskHex(level: RiskLevel | string): string {
  const map: Record<string, string> = {
    critical: 'var(--critical)',
    high: 'var(--high)',
    medium: 'var(--medium)',
    low: 'var(--low)',
    urgent_reflection: '#8B5CF6',    // Soft purple
    deep_reflection: '#6366F1',      // Indigo
    gentle_nudge: '#3B82F6',         // Blue
    observation: '#10B981'           // Emerald
  };
  return map[level] ?? 'var(--text-secondary)';
}

export function getDecisionClass(decision: Decision | string): string {
  const map: Record<string, string> = {
    BLOCK: 'decision-block',
    ESCALATE: 'decision-escalate',
    WARN: 'decision-warn',
    ALLOW: 'decision-allow',
    REFLECTION: 'decision-reflection',
    SELF_WARN: 'decision-reflection'
  };
  return map[decision] ?? '';
}

export function getThreatHex(score: number): string {
  if (score >= 0.85) return 'var(--critical)';
  if (score >= 0.70) return 'var(--high)';
  if (score >= 0.55) return 'var(--medium)';
  return 'var(--low)';
}
