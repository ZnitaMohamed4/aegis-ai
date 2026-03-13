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

export const MOCK_USERS: ParentUser[] = [
  {
    id: '1',
    full_name: 'Karim Benali',
    email: 'karim.benali@email.com',
    phone: '+212 6XX XXX X10',
    status: 'active',
    monitoring_active: true,
    alert_threshold: 0.75,
    sms_notifications: true,
    email_notifications: true,
    linked_child: {
      identifier: 'Child #A1',
      whatsapp_number: '+212 6XX XXX X01',
      risk_level: 'critical',
      whatsapp_connected: true
    },
    joined_at: 'Jan 15, 2026',
    last_login: '2 hr ago'
  },
  {
    id: '2',
    full_name: 'Samira Ouhbi',
    email: 'samira.ouhbi@email.com',
    phone: '+212 6XX XXX X11',
    status: 'active',
    monitoring_active: true,
    alert_threshold: 0.80,
    sms_notifications: false,
    email_notifications: true,
    linked_child: {
      identifier: 'Child #B2',
      whatsapp_number: '+212 6XX XXX X02',
      risk_level: 'high',
      whatsapp_connected: true
    },
    joined_at: 'Feb 3, 2026',
    last_login: '1 day ago'
  },
  {
    id: '3',
    full_name: 'Youssef Amine',
    email: 'youssef.amine@email.com',
    phone: '+212 6XX XXX X12',
    status: 'active',
    monitoring_active: false,
    alert_threshold: 0.70,
    sms_notifications: true,
    email_notifications: false,
    linked_child: {
      identifier: 'Child #C3',
      whatsapp_number: '+212 6XX XXX X03',
      risk_level: 'medium',
      whatsapp_connected: true
    },
    joined_at: 'Feb 10, 2026',
    last_login: '3 days ago'
  },
  {
    id: '4',
    full_name: 'Nadia Rachidi',
    email: 'nadia.rachidi@email.com',
    phone: '+212 6XX XXX X13',
    status: 'inactive',
    monitoring_active: false,
    alert_threshold: 0.75,
    sms_notifications: false,
    email_notifications: false,
    linked_child: null,
    joined_at: 'Mar 1, 2026',
    last_login: 'Never'
  },
  {
    id: '5',
    full_name: 'Hassan Tazi',
    email: 'hassan.tazi@email.com',
    phone: '+212 6XX XXX X14',
    status: 'suspended',
    monitoring_active: false,
    alert_threshold: 0.75,
    sms_notifications: true,
    email_notifications: true,
    linked_child: {
      identifier: 'Child #D4',
      whatsapp_number: '+212 6XX XXX X04',
      risk_level: 'low',
      whatsapp_connected: false
    },
    joined_at: 'Mar 5, 2026',
    last_login: '5 days ago'
  }
];
