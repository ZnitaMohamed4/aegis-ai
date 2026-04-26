export type ReportStatus = 'ready' | 'generating' | 'pending' | 'failed';
export type ReportType = 'summary' | 'full' | 'legal' | 'intelligence';
export type DeliveryChannel = 'email' | 'whatsapp' | 'both' | 'dashboard';

export interface Report {
  id: string;
  child?: string;
  child_name: string;
  requested_by?: string;
  report_type: ReportType;
  period_start: string;
  period_end: string;
  status: ReportStatus;
  delivery_channel: DeliveryChannel;
  flagged_legal: boolean;
  created_at: string;
  completed_at?: string;
  ai_narrative: string;
  pdf_file?: string;
  stats_json: {
    total_messages?: number;
    total_blocked?: number;
    unique_harassers?: number;
    escalations?: number;
    dominant_category?: string;
    risk_score_start?: number;
    risk_score_end?: number;
  };
  threat_actors?: {
    number: string;
    messages_sent: number;
    blocked: number;
    dominant_category: string;
    threat_score: number;
  }[];
}
