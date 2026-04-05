export type QueueReason = 'SCORE_AMBIGU' | 'LANGUE_NON_IDENTIFIABLE';
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface ChildContext {
  id: string;
  name: string;
  risk_level: RiskLevel;
  risk_score: number;
}

export interface PreviousMessage {
  content_preview: string;
  sent_at: string;
  is_blocked: boolean;
}

export interface ReviewItem {
  id: string;
  preview: string;
  full_preview: string;
  tentative_label: string;
  queue_reason: QueueReason;
  // All 4 scores
  confidence_score: number;
  toxicity_score: number;
  behavioral_risk_score: number;
  final_score: number;
  language: string;
  agents_used: string[];
  llm_explanation: string | null;
  submitted_at: string;
  contact_number: string;
  // Child context
  child: ChildContext;
  // Previous messages for context
  previous_messages: PreviousMessage[];
  // Audit trail (filled after review)
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export interface SimilarDecision {
  preview: string;
  decision: string;
  confidence: number;
}

// Mock similar past decisions keyed by tentative label
export const SIMILAR_DECISIONS: Record<string, SimilarDecision[]> = {
  'Verbal Harassment': [
    { preview: '"T\'es vraiment un déchet, dégage..."', decision: 'BLOCK', confidence: 0.89 },
    { preview: '"Personne ne veut traîner avec toi..."', decision: 'BLOCK', confidence: 0.72 },
    { preview: '"Haha tu fais pitié en fait..."', decision: 'ALLOW', confidence: 0.61 },
  ],
  'Threat': [
    { preview: '"Je vais te retrouver après les cours..."', decision: 'BLOCK', confidence: 0.94 },
    { preview: '"Fais gaffe à toi demain..."', decision: 'BLOCK', confidence: 0.83 },
    { preview: '"Si je te croise t\'es mort..."', decision: 'BLOCK', confidence: 0.91 },
  ],
  'Discrimination': [
    { preview: '"Les gens comme toi ne méritent..."', decision: 'BLOCK', confidence: 0.76 },
    { preview: '"Retourne d\'où tu viens..."', decision: 'BLOCK', confidence: 0.81 },
    { preview: '"You don\'t belong here..."', decision: 'ALLOW', confidence: 0.58 },
  ],
  'Sexual Harassment': [
    { preview: '"Envoie tes photos sinon..."', decision: 'BLOCK', confidence: 0.88 },
    { preview: '"T\'es trop belle pour traîner..."', decision: 'BLOCK', confidence: 0.69 },
    { preview: '"On devrait se voir en privé..."', decision: 'ALLOW', confidence: 0.52 },
  ],
  'Safe': [
    { preview: '"On se retrouve demain au parc?"', decision: 'ALLOW', confidence: 0.12 },
    { preview: '"T\'as fait tes devoirs?"', decision: 'ALLOW', confidence: 0.08 },
  ],
};

export const MOCK_REVIEW_ITEMS: ReviewItem[] = [
  {
    id: '1',
    preview: 'Haha t\'as vu sa tête sur la photo...',
    full_preview: 'Haha t\'as vu sa tête sur la photo que j\'ai postée ? Tout le monde se moque de toi maintenant, c\'est trop drôle.',
    tentative_label: 'Verbal Harassment',
    queue_reason: 'SCORE_AMBIGU',
    confidence_score: 0.68,
    toxicity_score: 0.71,
    behavioral_risk_score: 0.45,
    final_score: 0.62,
    language: 'FR',
    agents_used: ['Agent 1', 'Agent 2', 'Agent 3'],
    llm_explanation: 'Message contains indirect mockery and public humiliation. Sarcasm pattern detected. Confidence elevated from 0.61 to 0.68 after contextual analysis.',
    submitted_at: '2026-03-12T12:16:00',
    contact_number: '+212 6XX XXX X01',
    child: {
      id: 'child-1',
      name: 'Youssef B.',
      risk_level: 'medium',
      risk_score: 0.45
    },
    previous_messages: [
      { content_preview: 'T\'es où ? On t\'attend au parc', sent_at: '2026-03-12T12:10:00', is_blocked: false },
      { content_preview: 'Tu réponds jamais, t\'es bizarre', sent_at: '2026-03-12T12:12:00', is_blocked: false }
    ],
    reviewed_by: null,
    reviewed_at: null
  },
  {
    id: '2',
    preview: 'Je sais où tu habites, fais attention...',
    full_preview: 'Je sais où tu habites, fais attention à toi quand tu rentres. C\'est juste un conseil d\'ami.',
    tentative_label: 'Threat',
    queue_reason: 'SCORE_AMBIGU',
    confidence_score: 0.72,
    toxicity_score: 0.74,
    behavioral_risk_score: 0.68,
    final_score: 0.71,
    language: 'FR',
    agents_used: ['Agent 1', 'Agent 2', 'Agent 3'],
    llm_explanation: 'Implicit threat disguised as friendly advice. High ambiguity — could be interpreted as genuine concern. LLM flagged threatening undertone with location reference.',
    submitted_at: '2026-03-12T11:45:00',
    contact_number: '+212 6XX XXX X02',
    child: {
      id: 'child-2',
      name: 'Amina K.',
      risk_level: 'high',
      risk_score: 0.72
    },
    previous_messages: [
      { content_preview: 'On s\'est croisé ce matin, non?', sent_at: '2026-03-12T11:30:00', is_blocked: false },
      { content_preview: 'Tu devrais faire attention à qui tu parles', sent_at: '2026-03-12T11:40:00', is_blocked: false }
    ],
    reviewed_by: null,
    reviewed_at: null
  },
  {
    id: '3',
    preview: 'You people are all the same, always...',
    full_preview: 'You people are all the same, always causing problems wherever you go. Nobody wants you here.',
    tentative_label: 'Discrimination',
    queue_reason: 'SCORE_AMBIGU',
    confidence_score: 0.66,
    toxicity_score: 0.69,
    behavioral_risk_score: 0.52,
    final_score: 0.63,
    language: 'EN',
    agents_used: ['Agent 1', 'Agent 2', 'Agent 3'],
    llm_explanation: 'Generalized discriminatory statement targeting a group. "You people" pattern associated with racial/ethnic discrimination. Context ambiguous without prior messages.',
    submitted_at: '2026-03-12T10:55:00',
    contact_number: '+212 6XX XXX X03',
    child: {
      id: 'child-3',
      name: 'Sara M.',
      risk_level: 'low',
      risk_score: 0.22
    },
    previous_messages: [
      { content_preview: 'Why are you even in this group?', sent_at: '2026-03-12T10:45:00', is_blocked: false },
      { content_preview: 'Just leave, nobody asked you', sent_at: '2026-03-12T10:50:00', is_blocked: false }
    ],
    reviewed_by: null,
    reviewed_at: null
  },
  {
    id: '4',
    preview: 'أنت دائماً تفعل هذا، لماذا لا تختفي...',
    full_preview: 'أنت دائماً تفعل هذا، لماذا لا تختفي من حياتنا؟ لا أحد يريدك هنا.',
    tentative_label: 'Verbal Harassment',
    queue_reason: 'LANGUE_NON_IDENTIFIABLE',
    confidence_score: 0.70,
    toxicity_score: 0.73,
    behavioral_risk_score: 0.61,
    final_score: 0.68,
    language: 'unknown',
    agents_used: ['Agent 1', 'Agent 2', 'Agent 3'],
    llm_explanation: 'Social exclusion language detected. "Disappear from our lives" — isolation tactic common in harassment patterns. Language detection uncertain due to mixed script.',
    submitted_at: '2026-03-12T09:40:00',
    contact_number: '+212 6XX XXX X04',
    child: {
      id: 'child-4',
      name: 'Karim H.',
      risk_level: 'critical',
      risk_score: 0.88
    },
    previous_messages: [
      { content_preview: 'محد يبيك هنا، روح', sent_at: '2026-03-12T09:30:00', is_blocked: true },
      { content_preview: 'ليش ما ترد؟', sent_at: '2026-03-12T09:35:00', is_blocked: false }
    ],
    reviewed_by: null,
    reviewed_at: null
  },
  {
    id: '5',
    preview: 'C\'est marrant comme t\'es nul en cours...',
    full_preview: 'C\'est marrant comme t\'es nul en cours, même le prof te déteste. Tout le monde le voit.',
    tentative_label: 'Verbal Harassment',
    queue_reason: 'SCORE_AMBIGU',
    confidence_score: 0.67,
    toxicity_score: 0.70,
    behavioral_risk_score: 0.38,
    final_score: 0.58,
    language: 'FR',
    agents_used: ['Agent 1', 'Agent 2'],
    llm_explanation: null,
    submitted_at: '2026-03-12T09:20:00',
    contact_number: '+212 6XX XXX X05',
    child: {
      id: 'child-1',
      name: 'Youssef B.',
      risk_level: 'medium',
      risk_score: 0.45
    },
    previous_messages: [
      { content_preview: 'T\'as eu combien au contrôle?', sent_at: '2026-03-12T09:10:00', is_blocked: false },
      { content_preview: 'Haha même pas 10 je parie', sent_at: '2026-03-12T09:15:00', is_blocked: false }
    ],
    reviewed_by: null,
    reviewed_at: null
  }
];
