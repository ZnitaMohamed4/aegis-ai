import { DetectedLanguage, ModerationDecision } from './moderation.model';

export type ZoneKey = 'allow' | 'warn' | 'review' | 'block' | 'critical';
export type AgentStatus = 'ACTIVE' | 'DEGRADED' | 'OFFLINE';
export type LlmProviderId = 'groq' | 'mistral' | 'openai';
export type SimulationLanguage = 'auto' | DetectedLanguage;
export type FinalDecision = ModerationDecision | 'critical';

export interface DecisionBoundaries {
  warn: number;
  review: number;
  block: number;
  critical: number;
}

export interface DecisionZone {
  key: ZoneKey;
  label: string;
  min: number;
  max: number;
  action: string;
}

export interface ScoreWeights {
  toxicity: number;
  behavioral: number;
  llm: number;
}

export interface PipelineAgent {
  id: number;
  name: string;
  role: string;
  model: string;
  status: AgentStatus;
  latencyMs: number;
  enabled: boolean;
  triggerNote?: string;
  degradedWarning?: string;
}

export interface LlmProviderOption {
  label: string;
  value: LlmProviderId;
}

export interface SimulationSample {
  text: string;
  language: DetectedLanguage;
  toxicity: number;
  behavioral: number;
  explanation: string;
}

export interface SimulationResult {
  detectedLanguage: DetectedLanguage;
  toxicityScore: number;
  llmTriggered: boolean;
  behavioralScore: number;
  finalScore: number;
  decision: FinalDecision;
  explanation: string;
}
