import { Contact, ConversationMessage } from '@core/models';

export const EMMA_CONTACTS: Contact[] = [
  {
    id: 'emma-1',
    name: 'Emma L.',
    number: '+212 612 345 678',
    child_name: 'Emma L.',
    child_id: 'emma-child-id',
    parent_name: 'Emma\'s Dad',
    sender_name: 'Coach Sarah',
    sender_risk_score: 0.05,
    risk_level: 'low',
    plateforme: 'WhatsApp',
    is_first_contact: false,
    last_message: 'Don\'t forget practice tomorrow!',
    last_message_at: '10:30',
    total_messages: 156,
    blocked_count: 0,
    unread: 0
  },
  {
    id: 'emma-2',
    name: 'Emma L.',
    number: '+212 612 345 678',
    child_name: 'Emma L.',
    child_id: 'emma-child-id',
    parent_name: 'Emma\'s Dad',
    sender_name: 'Unknown Sender',
    sender_risk_score: 0.88,
    risk_level: 'high',
    plateforme: 'WhatsApp',
    is_first_contact: true,
    last_message: 'Blocked by Aegis AI',
    last_message_at: 'Yesterday',
    total_messages: 5,
    blocked_count: 5,
    unread: 0
  },
  {
    id: 'emma-3',
    name: 'Emma L.',
    number: '+212 612 345 678',
    child_name: 'Emma L.',
    child_id: 'emma-child-id',
    parent_name: 'Emma\'s Dad',
    sender_name: 'Lucas (Class)',
    sender_risk_score: 0.42,
    risk_level: 'medium',
    plateforme: 'WhatsApp',
    is_first_contact: false,
    last_message: 'Did u finish the homework?',
    last_message_at: 'Monday',
    total_messages: 89,
    blocked_count: 1,
    unread: 0
  }
];

export const EMMA_MESSAGES: Record<string, ConversationMessage[]> = {
  'emma-1': [
    {
      id: 'm1',
      content_preview: 'Great job today Emma!',
      direction: 'incoming',
      is_blocked: false,
      language: 'EN',
      sent_at: '09:00',
      decision: 'ALLOW',
      toxicity_score: 0.01,
      category: null,
      llm_triggered: false
    },
    {
      id: 'm2',
      content_preview: 'Thanks coach!',
      direction: 'outgoing',
      is_blocked: false,
      language: 'EN',
      sent_at: '09:15',
      decision: null,
      toxicity_score: null,
      category: null,
      llm_triggered: false
    },
    {
      id: 'm3',
      content_preview: 'Don\'t forget practice tomorrow at 4pm!',
      direction: 'incoming',
      is_blocked: false,
      language: 'EN',
      sent_at: '10:30',
      decision: 'ALLOW',
      toxicity_score: 0.01,
      category: null,
      llm_triggered: false
    }
  ],
  'emma-2': [
    {
      id: 'e1',
      content_preview: 'You should give me your address.',
      direction: 'incoming',
      is_blocked: true,
      language: 'EN',
      sent_at: '14:20',
      decision: 'BLOCK',
      toxicity_score: 0.85,
      category: 'Privacy Risk',
      llm_triggered: true
    },
    {
      id: 'e2',
      content_preview: 'Why won\'t you answer me?',
      direction: 'incoming',
      is_blocked: true,
      language: 'EN',
      sent_at: '14:25',
      decision: 'BLOCK',
      toxicity_score: 0.92,
      category: 'Harassment',
      llm_triggered: true
    }
  ],
  'emma-3': [
    {
      id: 'l1',
      content_preview: 'Hey Emma, have you done the math hw?',
      direction: 'incoming',
      is_blocked: false,
      language: 'EN',
      sent_at: '16:00',
      decision: 'ALLOW',
      toxicity_score: 0.02,
      category: null,
      llm_triggered: false
    },
    {
      id: 'l2',
      content_preview: 'Almost, it was hard lol',
      direction: 'outgoing',
      is_blocked: false,
      language: 'EN',
      sent_at: '16:10',
      decision: null,
      toxicity_score: null,
      category: null,
      llm_triggered: false
    }
  ]
};
