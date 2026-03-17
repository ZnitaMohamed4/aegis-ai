export type ReportStatus = 'ready' | 'generating' | 'pending';
export type ReportType = 'summary' | 'full' | 'legal';

export interface Report {
  id: string;
  child_identifier: string;
  requested_by: string;
  report_type: ReportType;
  period_start: string;
  period_end: string;
  status: ReportStatus;
  flagged_legal: boolean;
  requested_at: string;
  ai_narrative: string;
  stats: {
    total_messages: number;
    total_blocked: number;
    unique_harassers: number;
    escalations: number;
    dominant_category: string;
    risk_score_start: number;
    risk_score_end: number;
  };
  threat_actors: {
    number: string;
    messages_sent: number;
    blocked: number;
    dominant_category: string;
    threat_score: number;
  }[];
}
