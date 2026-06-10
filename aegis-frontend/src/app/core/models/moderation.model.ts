export type ModerationDecision = 'allow' | 'warn' | 'block' | 'escalate';
export type ReviewStatus = 'pending' | 'confirmed_block' | 'allowed';
export type DetectedLanguage = 'fr' | 'ar' | 'en' | 'darija' | 'unknown';

export interface ModerationRequest {
  id: string;
  content_preview: string;       // truncated, privacy-safe
  content_hash: string;          // SHA-256, never raw content
  detected_language: DetectedLanguage;
  requested_at: string;
  processing_time_ms: number;
  status: string;
}

export interface ModerationResult {
  id: string;
  moderation_request_id: string;
  toxicity_score: number;        // 0.0 → 1.0
  confidence_score: number;      // 0.0 → 1.0
  behavioral_risk_score: number; // 0.0 → 1.0
  final_label: string;
  decision: ModerationDecision;
  llm_triggered: boolean;        // true if confidence < 0.85
  llm_explanation: string | null;
  agents_used: string[];
  review_status: ReviewStatus | null;  // null = AI was confident, no review needed
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
}