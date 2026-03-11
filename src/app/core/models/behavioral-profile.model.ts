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