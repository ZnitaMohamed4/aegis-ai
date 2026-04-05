import { ModerationResult } from './moderation.model';
import { AlertSeverity } from './alert.model';

export interface Message {
  id: string;
  content_preview: string;
  content_hash: string;
  is_blocked: boolean;
  sent_at: string;
  moderation_result: ModerationResult | null;
}

export interface Conversation {
  id: string;
  child_id: string;
  contact_number: string;
  contact_name: string | null;
  last_message_at: string;
  total_messages: number;
  blocked_count: number;
  risk_level: AlertSeverity;
}

export interface Contact {
  id: string;
  name: string | null;
  number: string;
  child_name: string;
  child_id: string;
  parent_name: string;
  sender_name: string;
  sender_risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  plateforme: 'WhatsApp';
  is_first_contact: boolean;
  last_message: string;
  last_message_at: string;
  total_messages: number;
  blocked_count: number;
  unread: number;
}

export interface ConversationMessage {
  id: string;
  content_preview: string;
  direction: 'incoming' | 'outgoing';
  is_blocked: boolean;
  language: 'FR' | 'AR' | 'EN' | 'UNKNOWN';
  sent_at: string;
  decision: string | null;
  toxicity_score: number | null;
  category: string | null;
  llm_triggered: boolean;
}