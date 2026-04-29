export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';
export type AlertChannel = 'push' | 'email' | 'sms' | 'call';

export interface Alert {
  id: string;
  moderation_result_id: string;
  channel: AlertChannel;
  severity: AlertSeverity;
  content_preview: string;
  is_read: boolean;
  is_resolved: boolean;
  sent_at: string;
  resolved_at: string | null;
  parent_notified: boolean;
}

export interface MockAlert {
  id: string;
  preview: string;
  severity: AlertSeverity;
  category: string;
  decision: string;
  toxicity_score: number;
  confidence_score: number;
  llm_triggered: boolean;
  llm_explanation: string | null;
  is_resolved: boolean;
  sent_at: string;
  language: string;
  contact_number?: string;
}