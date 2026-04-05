export type AccountType = 'admin' | 'parent';
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface User {
  id: string;
  username: string;
  email: string;
  account_type: AccountType;
  language_preference: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MonitoredChild {
  id: string;
  full_name: string;
  whatsapp_number: string;
  risk_level: RiskLevel;
  risk_score: number;
  is_monitored: boolean;
  linked_at: string;
}

export interface ParentProfile {
  id: string;
  user: User;
  phone_number: string;
  alert_threshold: number;
  receive_sms_alerts: boolean;
  receive_email_alerts: boolean;
  monitored_children: MonitoredChild[];
}