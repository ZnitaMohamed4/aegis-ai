import { Contact, ConversationMessage } from '@core/models';

export const MOCK_CONTACTS: Contact[] = [
  {
    id: '1',
    raw_jid: '',
    name: 'Unknown',
    number: '+212 6XX XXX X01',
    child_name: 'Youssef Amrani',
    child_id: 'child-1',
    parent_name: 'Khalid Amrani',
    sender_name: 'Unknown sender #1',
    sender_risk_score: 0.91,
    risk_level: 'critical',
    plateforme: 'WhatsApp',
    is_first_contact: true,
    last_message: 'Je vais te retrouver après...',
    last_message_at: '08:02',
    total_messages: 24,
    blocked_count: 5,
    unread: 3
  },
  {
    id: '2',
    raw_jid: '',
    name: 'Unknown',
    number: '+212 6XX XXX X02',
    child_name: 'Sara Bennani',
    child_id: 'child-2',
    parent_name: 'Fatima Bennani',
    sender_name: 'Unknown sender #2',
    sender_risk_score: 0.78,
    risk_level: 'high',
    plateforme: 'WhatsApp',
    is_first_contact: false,
    last_message: 'T\'es vraiment nul...',
    last_message_at: '07:45',
    total_messages: 18,
    blocked_count: 3,
    unread: 1
  },
  {
    id: '3',
    raw_jid: '',
    name: 'Unknown',
    number: '+212 6XX XXX X03',
    child_name: 'Adam El Fassi',
    child_id: 'child-3',
    parent_name: 'Nadia El Fassi',
    sender_name: 'Unknown sender #3',
    sender_risk_score: 0.56,
    risk_level: 'medium',
    plateforme: 'WhatsApp',
    is_first_contact: false,
    last_message: 'Haha t\'as vu sa tête...',
    last_message_at: '07:30',
    total_messages: 12,
    blocked_count: 1,
    unread: 0
  },
  {
    id: '4',
    raw_jid: '',
    name: 'Unknown',
    number: '+212 6XX XXX X04',
    child_name: 'Amine Tazi',
    child_id: 'child-4',
    parent_name: 'Hassan Tazi',
    sender_name: 'Classmate #4',
    sender_risk_score: 0.19,
    risk_level: 'low',
    plateforme: 'WhatsApp',
    is_first_contact: false,
    last_message: 'On se retrouve demain ?',
    last_message_at: '06:55',
    total_messages: 8,
    blocked_count: 0,
    unread: 0
  }
];

export const MOCK_MESSAGES: Record<string, ConversationMessage[]> = {
  '1': [
    {
      id: '1a',
      content_preview: 'Salut, t\'as passé une bonne journée ?',
      direction: 'incoming',
      is_blocked: false,
      language: 'FR',
      sent_at: '07:30',
      decision: 'ALLOW',
      toxicity_score: 0.02,
      category: null,
      llm_triggered: false
    },
    {
      id: '1b',
      content_preview: 'Oui bien merci, et toi ?',
      direction: 'outgoing',
      is_blocked: false,
      language: 'FR',
      sent_at: '07:32',
      decision: null,
      toxicity_score: null,
      category: null,
      llm_triggered: false
    },
    {
      id: '1c',
      content_preview: 'Je sais où t\'habites, fais gaffe à toi.',
      direction: 'incoming',
      is_blocked: true,
      language: 'FR',
      sent_at: '07:45',
      decision: 'BLOCK',
      toxicity_score: 0.94,
      category: 'Threat',
      llm_triggered: false
    },
    {
      id: '1d',
      content_preview: 'T\'as vu mes messages ? Réponds.',
      direction: 'incoming',
      is_blocked: false,
      language: 'FR',
      sent_at: '07:55',
      decision: 'ALLOW',
      toxicity_score: 0.08,
      category: null,
      llm_triggered: false
    },
    {
      id: '1e',
      content_preview: 'Je vais te retrouver après les cours...',
      direction: 'incoming',
      is_blocked: true,
      language: 'FR',
      sent_at: '08:02',
      decision: 'ESCALATE',
      toxicity_score: 0.97,
      category: 'Threat',
      llm_triggered: false
    }
  ],
  '2': [
    {
      id: '2a',
      content_preview: 'Hey, tu fais quoi ce soir ?',
      direction: 'incoming',
      is_blocked: false,
      language: 'FR',
      sent_at: '07:00',
      decision: 'ALLOW',
      toxicity_score: 0.01,
      category: null,
      llm_triggered: false
    },
    {
      id: '2b',
      content_preview: 'Rien de spécial, pourquoi ?',
      direction: 'outgoing',
      is_blocked: false,
      language: 'FR',
      sent_at: '07:10',
      decision: null,
      toxicity_score: null,
      category: null,
      llm_triggered: false
    },
    {
      id: '2c',
      content_preview: 'T\'es vraiment nul, personne ne t\'aime dans cette école.',
      direction: 'incoming',
      is_blocked: true,
      language: 'FR',
      sent_at: '07:45',
      decision: 'BLOCK',
      toxicity_score: 0.88,
      category: 'Verbal Harassment',
      llm_triggered: false
    }
  ],
  '3': [
    {
      id: '3a',
      content_preview: 'Haha t\'as vu sa tête sur la photo ?',
      direction: 'incoming',
      is_blocked: true,
      language: 'FR',
      sent_at: '07:30',
      decision: 'WARN',
      toxicity_score: 0.71,
      category: 'Verbal Harassment',
      llm_triggered: true
    },
    {
      id: '3b',
      content_preview: 'De quoi tu parles ?',
      direction: 'outgoing',
      is_blocked: false,
      language: 'FR',
      sent_at: '07:35',
      decision: null,
      toxicity_score: null,
      category: null,
      llm_triggered: false
    }
  ],
  '4': [
    {
      id: '4a',
      content_preview: 'On se retrouve demain au parc ?',
      direction: 'incoming',
      is_blocked: false,
      language: 'FR',
      sent_at: '06:55',
      decision: 'ALLOW',
      toxicity_score: 0.01,
      category: null,
      llm_triggered: false
    },
    {
      id: '4b',
      content_preview: 'Oui bonne idée, à quelle heure ?',
      direction: 'outgoing',
      is_blocked: false,
      language: 'FR',
      sent_at: '07:00',
      decision: null,
      toxicity_score: null,
      category: null,
      llm_triggered: false
    }
  ]
};
