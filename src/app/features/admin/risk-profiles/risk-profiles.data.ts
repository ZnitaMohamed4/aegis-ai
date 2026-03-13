export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface RiskSnapshot {
  date_snapshot: string;
  score_risque_snapshot: number;
  alert_id: string | null;
}

export interface CategoryBreakdown {
  verbal: number;
  threat: number;
  sexual: number;
  discrimination: number;
}

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
  nombre_cibles_differentes: number;
  other_monitored_children_count: number;
  dominant_category: string;
  toxicity_trend: number[];
  last_seen: string;
  related_child_ids: string[];
}

export const MOCK_CHILDREN: ChildProfile[] = [
  {
    id: '1',
    identifier: 'Child #A1',
    whatsapp_number: '+212 6XX XXX X01',
    parent_user_id: 'u-parent-1',
    date_naissance: '2012-04-18',
    nom_ecole: 'Ibn Rochd School',
    niveau_scolaire: '7th Grade',
    victim_risk_level: 'critical',
    victim_risk_score: 0.91,
    total_incoming: 142,
    total_blocked: 18,
    total_messages_bloques_envoyes: 4,
    activite_nocturne: 0.62,
    unique_harassers: 3,
    escalation_count: 5,
    most_common_category: 'Threat',
    risk_trend: [0.45, 0.52, 0.61, 0.70, 0.78, 0.84, 0.91],
    snapshots: [
      { date_snapshot: 'Mar 05', score_risque_snapshot: 0.45, alert_id: null },
      { date_snapshot: 'Mar 06', score_risque_snapshot: 0.52, alert_id: null },
      { date_snapshot: 'Mar 07', score_risque_snapshot: 0.61, alert_id: 'a-101' },
      { date_snapshot: 'Mar 08', score_risque_snapshot: 0.70, alert_id: null },
      { date_snapshot: 'Mar 09', score_risque_snapshot: 0.78, alert_id: 'a-118' },
      { date_snapshot: 'Mar 10', score_risque_snapshot: 0.84, alert_id: null },
      { date_snapshot: 'Mar 11', score_risque_snapshot: 0.91, alert_id: 'a-133' }
    ],
    category_breakdown: {
      verbal: 0.23,
      threat: 0.49,
      sexual: 0.18,
      discrimination: 0.10
    },
    last_activity: '2 min ago',
    monitored_since: 'Jan 15, 2026'
  },
  {
    id: '2',
    identifier: 'Child #B2',
    whatsapp_number: '+212 6XX XXX X02',
    parent_user_id: 'u-parent-2',
    date_naissance: '2011-11-03',
    nom_ecole: 'Ibn Rochd School',
    niveau_scolaire: '8th Grade',
    victim_risk_level: 'high',
    victim_risk_score: 0.74,
    total_incoming: 98,
    total_blocked: 9,
    total_messages_bloques_envoyes: 1,
    activite_nocturne: 0.41,
    unique_harassers: 1,
    escalation_count: 2,
    most_common_category: 'Verbal Harassment',
    risk_trend: [0.30, 0.38, 0.45, 0.55, 0.61, 0.68, 0.74],
    snapshots: [
      { date_snapshot: 'Mar 05', score_risque_snapshot: 0.30, alert_id: null },
      { date_snapshot: 'Mar 06', score_risque_snapshot: 0.38, alert_id: null },
      { date_snapshot: 'Mar 07', score_risque_snapshot: 0.45, alert_id: 'a-142' },
      { date_snapshot: 'Mar 08', score_risque_snapshot: 0.55, alert_id: null },
      { date_snapshot: 'Mar 09', score_risque_snapshot: 0.61, alert_id: null },
      { date_snapshot: 'Mar 10', score_risque_snapshot: 0.68, alert_id: 'a-150' },
      { date_snapshot: 'Mar 11', score_risque_snapshot: 0.74, alert_id: null }
    ],
    category_breakdown: {
      verbal: 0.58,
      threat: 0.24,
      sexual: 0.11,
      discrimination: 0.07
    },
    last_activity: '1 hr ago',
    monitored_since: 'Feb 3, 2026'
  },
  {
    id: '3',
    identifier: 'Child #C3',
    whatsapp_number: '+212 6XX XXX X03',
    parent_user_id: 'u-parent-3',
    date_naissance: '2013-06-22',
    nom_ecole: 'Al Amal College',
    niveau_scolaire: '6th Grade',
    victim_risk_level: 'medium',
    victim_risk_score: 0.51,
    total_incoming: 67,
    total_blocked: 4,
    total_messages_bloques_envoyes: 0,
    activite_nocturne: 0.24,
    unique_harassers: 1,
    escalation_count: 1,
    most_common_category: 'Discrimination',
    risk_trend: [0.20, 0.28, 0.35, 0.40, 0.44, 0.48, 0.51],
    snapshots: [
      { date_snapshot: 'Mar 05', score_risque_snapshot: 0.20, alert_id: null },
      { date_snapshot: 'Mar 06', score_risque_snapshot: 0.28, alert_id: null },
      { date_snapshot: 'Mar 07', score_risque_snapshot: 0.35, alert_id: null },
      { date_snapshot: 'Mar 08', score_risque_snapshot: 0.40, alert_id: null },
      { date_snapshot: 'Mar 09', score_risque_snapshot: 0.44, alert_id: 'a-165' },
      { date_snapshot: 'Mar 10', score_risque_snapshot: 0.48, alert_id: null },
      { date_snapshot: 'Mar 11', score_risque_snapshot: 0.51, alert_id: null }
    ],
    category_breakdown: {
      verbal: 0.19,
      threat: 0.21,
      sexual: 0.05,
      discrimination: 0.55
    },
    last_activity: '3 hr ago',
    monitored_since: 'Feb 10, 2026'
  },
  {
    id: '4',
    identifier: 'Child #D4',
    whatsapp_number: '+212 6XX XXX X04',
    parent_user_id: 'u-parent-4',
    date_naissance: '2010-09-14',
    nom_ecole: 'Lycée Al Farabi',
    niveau_scolaire: '9th Grade',
    victim_risk_level: 'low',
    victim_risk_score: 0.18,
    total_incoming: 45,
    total_blocked: 1,
    total_messages_bloques_envoyes: 2,
    activite_nocturne: 0.13,
    unique_harassers: 0,
    escalation_count: 0,
    most_common_category: 'None',
    risk_trend: [0.10, 0.12, 0.15, 0.14, 0.16, 0.17, 0.18],
    snapshots: [
      { date_snapshot: 'Mar 05', score_risque_snapshot: 0.10, alert_id: null },
      { date_snapshot: 'Mar 06', score_risque_snapshot: 0.12, alert_id: null },
      { date_snapshot: 'Mar 07', score_risque_snapshot: 0.15, alert_id: null },
      { date_snapshot: 'Mar 08', score_risque_snapshot: 0.14, alert_id: null },
      { date_snapshot: 'Mar 09', score_risque_snapshot: 0.16, alert_id: null },
      { date_snapshot: 'Mar 10', score_risque_snapshot: 0.17, alert_id: null },
      { date_snapshot: 'Mar 11', score_risque_snapshot: 0.18, alert_id: null }
    ],
    category_breakdown: {
      verbal: 0.42,
      threat: 0.18,
      sexual: 0.08,
      discrimination: 0.32
    },
    last_activity: '5 hr ago',
    monitored_since: 'Mar 1, 2026'
  }
];

export const MOCK_CONTACTS: ContactProfile[] = [
  {
    id: 'c1',
    whatsapp_number: '+212 6XX XXX X91',
    threat_level: 'critical',
    threat_score: 0.94,
    total_sent: 38,
    total_blocked: 14,
    block_ratio: 0.368,
    escalation_count: 4,
    night_activity_ratio: 0.71,
    activite_nocturne: 0.71,
    avg_toxicity: 0.89,
    repeated_targeting: true,
    targets_count: 3,
    nombre_cibles_differentes: 3,
    other_monitored_children_count: 2,
    dominant_category: 'Threat',
    toxicity_trend: [0.50, 0.60, 0.72, 0.78, 0.83, 0.89, 0.94],
    last_seen: '2 min ago',
    related_child_ids: ['1', '2', '3']
  },
  {
    id: 'c2',
    whatsapp_number: '+212 6XX XXX X92',
    threat_level: 'high',
    threat_score: 0.77,
    total_sent: 25,
    total_blocked: 8,
    block_ratio: 0.320,
    escalation_count: 2,
    night_activity_ratio: 0.44,
    activite_nocturne: 0.44,
    avg_toxicity: 0.74,
    repeated_targeting: true,
    targets_count: 2,
    nombre_cibles_differentes: 2,
    other_monitored_children_count: 1,
    dominant_category: 'Verbal Harassment',
    toxicity_trend: [0.30, 0.40, 0.50, 0.58, 0.65, 0.71, 0.77],
    last_seen: '1 hr ago',
    related_child_ids: ['2', '4']
  },
  {
    id: 'c3',
    whatsapp_number: '+212 6XX XXX X93',
    threat_level: 'medium',
    threat_score: 0.55,
    total_sent: 14,
    total_blocked: 3,
    block_ratio: 0.214,
    escalation_count: 1,
    night_activity_ratio: 0.28,
    activite_nocturne: 0.28,
    avg_toxicity: 0.58,
    repeated_targeting: false,
    targets_count: 1,
    nombre_cibles_differentes: 1,
    other_monitored_children_count: 0,
    dominant_category: 'Discrimination',
    toxicity_trend: [0.20, 0.28, 0.35, 0.42, 0.46, 0.51, 0.55],
    last_seen: '4 hr ago',
    related_child_ids: ['3']
  },
  {
    id: 'c4',
    whatsapp_number: '+212 6XX XXX X94',
    threat_level: 'low',
    threat_score: 0.21,
    total_sent: 10,
    total_blocked: 1,
    block_ratio: 0.100,
    escalation_count: 0,
    night_activity_ratio: 0.10,
    activite_nocturne: 0.10,
    avg_toxicity: 0.19,
    repeated_targeting: false,
    targets_count: 1,
    nombre_cibles_differentes: 1,
    other_monitored_children_count: 0,
    dominant_category: 'Verbal Harassment',
    toxicity_trend: [0.10, 0.14, 0.16, 0.18, 0.19, 0.20, 0.21],
    last_seen: '6 hr ago',
    related_child_ids: ['4']
  }
];
