import {
	AgentStatus,
	DecisionBoundaries,
	FinalDecision,
	LlmProviderId,
	PipelineAgent,
	SimulationSample,
	ZoneKey,
} from '@core/models/ai-config.model';

export interface DecisionZoneMeta {
	key: ZoneKey;
	label: string;
	action: string;
	rangeLabel: string;
	tone: 'allow' | 'warn' | 'review' | 'block' | 'critical';
}

export interface ProviderCard {
	id: LlmProviderId;
	name: string;
	subtitle: string;
}

export interface ProviderModelOption {
	label: string;
	value: string;
}

export interface LanguageTab {
	key: 'auto' | 'fr' | 'ar' | 'en' | 'darija';
	label: string;
}

export const DEFAULT_BOUNDARIES: DecisionBoundaries = {
	warn: 0.5,
	review: 0.65,
	block: 0.75,
	critical: 0.9,
};

export const DECISION_ZONES: DecisionZoneMeta[] = [
	{ key: 'allow', label: 'AUTORISER', action: 'Allow and archive', rangeLabel: '< 0.50', tone: 'allow' },
	{ key: 'warn', label: 'AVERTIR', action: 'Soft warning to sender', rangeLabel: '0.50 - 0.65', tone: 'warn' },
	{ key: 'review', label: 'REVISER', action: 'Send to Review Queue', rangeLabel: '0.65 - 0.75', tone: 'review' },
	{ key: 'block', label: 'BLOQUER', action: 'Block + notify parent app', rangeLabel: '0.75 - 0.90', tone: 'block' },
	{ key: 'critical', label: 'CRITIQUE', action: 'SMS + phone escalation', rangeLabel: '>= 0.90', tone: 'critical' },
];

export const AGENT_CARDS: PipelineAgent[] = [
	{ id: 1, name: 'Regex Gate', role: 'Pattern detection', model: 'Rule Engine v3', status: 'ACTIVE', latencyMs: 42, enabled: true },
	{ id: 2, name: 'ML Classification', role: 'Toxicity scoring', model: 'XLM-RoBERTa', status: 'ACTIVE', latencyMs: 124, enabled: true },
	{
		id: 3,
		name: 'Semantic LLM',
		role: 'Context review',
		model: 'Groq/Mistral',
		status: 'DEGRADED',
		latencyMs: 318,
		enabled: true,
		triggerNote: 'Conditional - triggers if confidence < 0.85',
		degradedWarning: 'Groq API unreachable - falling back to Agent 2',
	},
	{ id: 4, name: 'Behavioral Engine', role: 'Victim risk model', model: 'Random Forest', status: 'ACTIVE', latencyMs: 176, enabled: true },
	{ id: 5, name: 'Decision Orchestrator', role: 'Final policy output', model: 'Policy Runtime', status: 'ACTIVE', latencyMs: 30, enabled: true },
];

export const PROVIDER_CARDS: ProviderCard[] = [
	{ id: 'groq', name: 'Groq', subtitle: 'Low latency routing' },
	{ id: 'mistral', name: 'Mistral', subtitle: 'General-purpose safety' },
	{ id: 'openai', name: 'OpenAI', subtitle: 'High accuracy fallback' },
];

export const PROVIDER_MODELS: Record<LlmProviderId, ProviderModelOption[]> = {
	groq: [
		{ label: 'mixtral-8x7b-32768', value: 'mixtral-8x7b-32768' },
		{ label: 'llama3-70b-8192', value: 'llama3-70b-8192' },
		{ label: 'gemma2-9b-it', value: 'gemma2-9b-it' },
	],
	mistral: [
		{ label: 'mistral-large-latest', value: 'mistral-large-latest' },
		{ label: 'mistral-small-latest', value: 'mistral-small-latest' },
		{ label: 'open-mixtral-8x7b', value: 'open-mixtral-8x7b' },
	],
	openai: [
		{ label: 'gpt-4o', value: 'gpt-4o' },
		{ label: 'gpt-4-turbo', value: 'gpt-4-turbo' },
		{ label: 'gpt-3.5-turbo', value: 'gpt-3.5-turbo' },
	],
};

export const LANGUAGE_TABS: LanguageTab[] = [
	{ key: 'auto', label: 'Auto-detect' },
	{ key: 'fr', label: 'FR' },
	{ key: 'ar', label: 'AR' },
	{ key: 'en', label: 'EN' },
	{ key: 'darija', label: '🇲🇦 Darija' },
];

export const SIMULATION_SAMPLES: SimulationSample[] = [
	{ text: 'je vais te trouver', language: 'fr', toxicity: 0.78, behavioral: 0.74, explanation: 'Threatening phrasing detected in French.' },
	{ text: 'this is our secret', language: 'en', toxicity: 0.64, behavioral: 0.71, explanation: 'Grooming-style secrecy cue detected.' },
	{ text: 'سأؤذيك', language: 'ar', toxicity: 0.93, behavioral: 0.89, explanation: 'Direct violent threat found in Arabic.' },
	{ text: 'nta zbil w mamak 3ahra', language: 'darija', toxicity: 0.88, behavioral: 0.55, explanation: 'Offensive Darija in Arabizi → M1D (DarijaBERT) → BLOCK' },
	{ text: 'salam labas 3lik? kif dayr', language: 'darija', toxicity: 0.05, behavioral: 0.02, explanation: 'Safe Darija greeting in Arabizi → M1D → ALLOW' },
	{ text: 'غادي نضربك حتى تموت', language: 'darija', toxicity: 0.85, behavioral: 0.70, explanation: 'Threatening Darija in Arabic script → M1D → ESCALATE' },
];

export const DECISION_LABELS: Record<FinalDecision, string> = {
	allow: 'AUTORISER',
	warn: 'AVERTIR',
	escalate: 'REVISER',
	block: 'BLOQUER',
	critical: 'CRITIQUE',
};

export const AGENT_STATUS_TONE: Record<AgentStatus, 'good' | 'warn' | 'bad'> = {
	ACTIVE: 'good',
	DEGRADED: 'warn',
	OFFLINE: 'bad',
};

// ════════════════════════════════════════════════════════════════
//  BAYESIAN NETWORK VISUALIZATION DATA
// ════════════════════════════════════════════════════════════════

export interface BnObservableDef {
  id: string;
  label: string;
  states: string[];
  pathway: string[];
}

export interface BnPathwayDef {
  id: string;
  label: string;
  color: string;
}

export interface BnEdgeDef {
  from: string;
  to: string;
}

export const BN_OBSERVABLES: BnObservableDef[] = [
  { id: 'Stranger',            label: 'Stranger',        states: ['NO', 'YES'],                          pathway: ['grooming'] },
  { id: 'ChildInitiated',      label: 'Child Initiated', states: ['NO', 'YES'],                          pathway: ['grooming'] },
  { id: 'SharedGroupsCount',   label: 'Shared Groups',   states: ['ZERO', 'ONE', 'MANY'],               pathway: ['grooming'] },
  { id: 'NightActive',         label: 'Night Active',    states: ['LOW', 'MEDIUM', 'HIGH'],             pathway: ['grooming'] },
  { id: 'UpwardCorrection',    label: 'Upward Corr.',    states: ['LOW', 'MEDIUM', 'HIGH'],             pathway: ['grooming'] },
  { id: 'ToxicityLevel',       label: 'Toxicity',        states: ['CLEAN', 'MILD', 'MODERATE', 'SEVERE'], pathway: ['bully'] },
  { id: 'BlockRatio',          label: 'Block Ratio',     states: ['LOW', 'MEDIUM', 'HIGH'],             pathway: ['bully'] },
  { id: 'TargetBreadth',       label: 'Target Breadth',  states: ['FEW', 'SOME', 'MANY'],               pathway: ['bully', 'troll'] },
  { id: 'DownwardCorrection',  label: 'Downward Corr.',  states: ['LOW', 'MEDIUM', 'HIGH'],             pathway: ['grooming', 'bully'] },
  { id: 'MessageBehavior',     label: 'Msg Behavior',    states: ['CALM', 'ACTIVE', 'BURSTY'],          pathway: ['troll'] },
  { id: 'MessageStyle',        label: 'Msg Style',       states: ['SHORT', 'MEDIUM', 'LONG'],           pathway: ['grooming', 'troll'] },
  { id: 'ThreatCategory',      label: 'Threat Cat.',     states: ['SAFE', 'VERBAL', 'THREAT', 'SEXUAL', 'DISCRIMINATION'], pathway: ['grooming', 'bully'] },
];

export const BN_PATHWAYS: BnPathwayDef[] = [
  { id: 'GroomingRisk', label: 'Grooming Risk', color: '#f43f5e' },
  { id: 'BullyRisk',    label: 'Bully Risk',    color: '#f59e0b' },
  { id: 'TrollRisk',    label: 'Troll Risk',    color: '#8b5cf6' },
];

export const BN_EDGES: BnEdgeDef[] = [
  // Grooming pathway (8 edges)
  { from: 'Stranger',           to: 'GroomingRisk' },
  { from: 'ChildInitiated',     to: 'GroomingRisk' },
  { from: 'SharedGroupsCount',  to: 'GroomingRisk' },
  { from: 'NightActive',        to: 'GroomingRisk' },
  { from: 'UpwardCorrection',   to: 'GroomingRisk' },
  { from: 'DownwardCorrection', to: 'GroomingRisk' },
  { from: 'MessageStyle',       to: 'GroomingRisk' },
  { from: 'ThreatCategory',     to: 'GroomingRisk' },
  // Bully pathway (5 edges)
  { from: 'ToxicityLevel',      to: 'BullyRisk' },
  { from: 'BlockRatio',         to: 'BullyRisk' },
  { from: 'TargetBreadth',      to: 'BullyRisk' },
  { from: 'ThreatCategory',     to: 'BullyRisk' },
  { from: 'DownwardCorrection', to: 'BullyRisk' },
  // Troll pathway (4 edges)
  { from: 'MessageBehavior',    to: 'TrollRisk' },
  { from: 'TargetBreadth',      to: 'TrollRisk' },
  { from: 'Stranger',           to: 'TrollRisk' },
  { from: 'MessageStyle',       to: 'TrollRisk' },
  // Output edges
  { from: 'GroomingRisk',       to: 'OverallRisk' },
  { from: 'BullyRisk',          to: 'OverallRisk' },
  { from: 'TrollRisk',          to: 'OverallRisk' },
];

/** Pathway color map for quick lookups */
export const BN_PATHWAY_COLORS: Record<string, string> = {
  grooming: '#f43f5e',
  bully: '#f59e0b',
  troll: '#8b5cf6',
};
