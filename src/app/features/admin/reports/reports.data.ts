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

export const MOCK_REPORTS: Report[] = [
  {
    id: 'RPT-001',
    child_identifier: 'Child #A1',
    requested_by: 'Karim Benali',
    report_type: 'legal',
    period_start: 'Mar 1, 2026',
    period_end: 'Mar 11, 2026',
    status: 'ready',
    flagged_legal: true,
    requested_at: '2 hr ago',
    ai_narrative: 'During the period March 1–11, 2026, Child #A1 received 142 messages from 3 distinct contacts. A total of 18 messages were blocked by the AI pipeline, representing a 12.7% block ratio. The dominant threat type was direct threats, with 5 escalation events requiring immediate parental notification. The child\'s risk score escalated from 0.45 to 0.91 over this period, indicating a rapidly deteriorating situation. Immediate intervention is strongly recommended.',
    stats: {
      total_messages: 142,
      total_blocked: 18,
      unique_harassers: 3,
      escalations: 5,
      dominant_category: 'Threat',
      risk_score_start: 0.45,
      risk_score_end: 0.91
    },
    threat_actors: [
      { number: '+212 6XX XXX X91', messages_sent: 38, blocked: 14, dominant_category: 'Threat', threat_score: 0.94 },
      { number: '+212 6XX XXX X92', messages_sent: 25, blocked: 8, dominant_category: 'Verbal Harassment', threat_score: 0.77 },
      { number: '+212 6XX XXX X93', messages_sent: 14, blocked: 3, dominant_category: 'Discrimination', threat_score: 0.55 }
    ]
  },
  {
    id: 'RPT-002',
    child_identifier: 'Child #B2',
    requested_by: 'Samira Ouhbi',
    report_type: 'full',
    period_start: 'Feb 25, 2026',
    period_end: 'Mar 4, 2026',
    status: 'ready',
    flagged_legal: false,
    requested_at: '1 day ago',
    ai_narrative: 'During the period February 25 – March 4, 2026, Child #B2 received 98 messages from 1 contact. 9 messages were blocked, primarily categorized as verbal harassment. The situation shows a pattern of repeated targeting by a single contact, which is a strong behavioral indicator of persistent bullying.',
    stats: {
      total_messages: 98,
      total_blocked: 9,
      unique_harassers: 1,
      escalations: 2,
      dominant_category: 'Verbal Harassment',
      risk_score_start: 0.30,
      risk_score_end: 0.74
    },
    threat_actors: [
      { number: '+212 6XX XXX X92', messages_sent: 25, blocked: 8, dominant_category: 'Verbal Harassment', threat_score: 0.77 }
    ]
  },
  {
    id: 'RPT-003',
    child_identifier: 'Child #A1',
    requested_by: 'Karim Benali',
    report_type: 'summary',
    period_start: 'Feb 1, 2026',
    period_end: 'Feb 28, 2026',
    status: 'generating',
    flagged_legal: false,
    requested_at: '5 min ago',
    ai_narrative: '',
    stats: {
      total_messages: 0,
      total_blocked: 0,
      unique_harassers: 0,
      escalations: 0,
      dominant_category: '-',
      risk_score_start: 0,
      risk_score_end: 0
    },
    threat_actors: []
  }
];
