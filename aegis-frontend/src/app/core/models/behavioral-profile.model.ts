import { RiskLevel } from './user.model';

export interface BehavioralProfile {
  id: string;
  child_id: string;
  total_messages: number;
  total_blocked: number;
  block_ratio: number;
  avg_toxicity_score: number;
  escalation_count: number;
  repeated_harassers_count: number;
  risk_score: number;
  night_activity_ratio: number;
  last_updated: string;
}

export interface BehavioralSnapshot {
  date: string;
  message_count: number;
  blocked_count: number;
  risk_score: number;
}

export interface RiskSnapshot {
  date_snapshot: string;
  score_risque_snapshot: number;
  alert_id: string | null;
}

export type CategoryBreakdown = Record<string, number>;

export interface ChildProfile {
  id: string;
  identifier: string;
  whatsapp_number: string;
  parent_user_id: string;
  date_naissance: string;
  nom_ecole: string;
  niveau_scolaire: string;

  victim_risk_level: RiskLevel;
  victim_risk_score: number;
  total_incoming: number;
  total_blocked: number;
  total_messages_bloques_envoyes: number;
  activite_nocturne: number;
  unique_harassers: number;
  escalation_count: number;
  most_common_category: string;
  risk_trend: number[];
  snapshots: RiskSnapshot[];
  category_breakdown: CategoryBreakdown;
  last_activity: string;
  monitored_since: string;
}

export interface ContactProfile {
  id: string;
  raw_jid: string;
  whatsapp_number: string;
  threat_level: RiskLevel;
  threat_score: number;
  total_sent: number;
  total_blocked: number;
  block_ratio: number;
  escalation_count: number;
  night_activity_ratio: number;
  activite_nocturne: number;
  avg_toxicity: number;
  repeated_targeting: boolean;
  targets_count: number;
  is_stranger?: boolean;
  child_initiated?: boolean;
  nombre_cibles_differentes: number;
  other_monitored_children_count: number;
  dominant_category: string;
  toxicity_trend: number[];
  last_seen: string;
  related_child_ids: string[];

  // Bayesian Network output
  archetype?: string;
  grooming_prob?: number;
  bully_prob?: number;
  troll_prob?: number;
}