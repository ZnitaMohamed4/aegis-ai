import { AlertSeverity } from '@core/models';

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
}

export const MOCK_ALERTS: MockAlert[] = [
  {
    id: '1',
    preview: 'Je vais te retrouver après les cours...',
    severity: 'critical',
    category: 'Threat',
    decision: 'BLOCK',
    toxicity_score: 0.97,
    confidence_score: 0.95,
    llm_triggered: false,
    llm_explanation: null,
    is_resolved: false,
    sent_at: '2026-03-11T08:02:00',
    language: 'FR'
  },
  {
    id: '2',
    preview: 'T\'es vraiment nul, personne ne t\'aime...',
    severity: 'high',
    category: 'Verbal Harassment',
    decision: 'BLOCK',
    toxicity_score: 0.88,
    confidence_score: 0.91,
    llm_triggered: false,
    llm_explanation: null,
    is_resolved: false,
    sent_at: '2026-03-11T07:45:00',
    language: 'FR'
  },
  {
    id: '3',
    preview: 'Envoie moi tes photos sinon je montre...',
    severity: 'critical',
    category: 'Sexual Harassment',
    decision: 'ESCALATE',
    toxicity_score: 0.99,
    confidence_score: 0.97,
    llm_triggered: false,
    llm_explanation: null,
    is_resolved: false,
    sent_at: '2026-03-11T07:26:00',
    language: 'FR'
  },
  {
    id: '4',
    preview: 'Les gens comme toi ne méritent pas...',
    severity: 'medium',
    category: 'Discrimination',
    decision: 'WARN',
    toxicity_score: 0.71,
    confidence_score: 0.68,
    llm_triggered: true,
    llm_explanation: 'Message contains implicit discriminatory language targeting ethnic background. Sarcasm detected — confidence boosted after LLM analysis.',
    is_resolved: false,
    sent_at: '2026-03-11T07:00:00',
    language: 'FR'
  },
  {
    id: '5',
    preview: 'أنت غبي ولا أحد يحبك في المدرسة',
    severity: 'high',
    category: 'Verbal Harassment',
    decision: 'BLOCK',
    toxicity_score: 0.86,
    confidence_score: 0.89,
    llm_triggered: false,
    llm_explanation: null,
    is_resolved: true,
    sent_at: '2026-03-11T06:30:00',
    language: 'AR'
  },
  {
    id: '6',
    preview: 'You are such a loser, nobody wants...',
    severity: 'medium',
    category: 'Verbal Harassment',
    decision: 'WARN',
    toxicity_score: 0.69,
    confidence_score: 0.72,
    llm_triggered: true,
    llm_explanation: 'Borderline case. LLM detected repeated targeting pattern. Elevated from low to medium severity.',
    is_resolved: true,
    sent_at: '2026-03-11T06:00:00',
    language: 'EN'
  }
];
