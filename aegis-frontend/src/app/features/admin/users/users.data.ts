export type AccountStatus = 'active' | 'inactive' | 'suspended';

export interface LinkedChild {
  identifier: string;
  whatsapp_number: string;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  whatsapp_connected: boolean;
}

export interface ParentUser {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  status: AccountStatus;
  monitoring_active: boolean;
  alert_threshold: number;
  sms_notifications: boolean;
  email_notifications: boolean;
  linked_child: LinkedChild | null;
  joined_at: string;
  last_login: string;
}
