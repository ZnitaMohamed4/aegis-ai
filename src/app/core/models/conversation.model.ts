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