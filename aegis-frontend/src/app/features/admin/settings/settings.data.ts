export interface ThemePreset {
  id: 'teal' | 'cyan' | 'rose' | 'indigo' | 'emerald' | 'graphite' | 'blue' | 'security';
  label: string;
  accent: string;
  bgPreview: string;
}

export interface RetentionSettings {
  messagesLogDays: number;
  blockedMessagesDays: number;
  alertHistoryDays: number;
  riskProfileHistoryDays: number;
}

export interface NotificationDefaults {
  emailNotifications: boolean;
  inAppNotifications: boolean;
  notifyOnBlock: boolean;
  notifyOnEscalate: boolean;
  notifyOnWarn: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
}

export interface ModerationDefaults {
  defaultLanguage: 'auto' | 'fr' | 'ar' | 'en';
  autoResolveAllow: boolean;
  rateLimitThreshold: number;
  parentPortalAccess: boolean;
}

export interface AdminAccountSettings {
  displayName: string;
  email: string;
  lastLogin: string;
}

export interface ThemeVariableSet {
  light: Record<string, string>;
  dark: Record<string, string>;
}

export const THEME_PRESETS: ThemePreset[] = [
  { id: 'teal', label: 'Midnight Teal', accent: '#14B8A6', bgPreview: '#0A1118' },
  { id: 'cyan', label: 'Arctic Cyan', accent: '#06B6D4', bgPreview: '#081217' },
  { id: 'rose', label: 'Sunset Rose', accent: '#EC4899', bgPreview: '#120A10' },
  { id: 'indigo', label: 'Indigo Analytics', accent: '#6366F1', bgPreview: '#0F1220' },
  { id: 'emerald', label: 'Emerald Guard', accent: '#10B981', bgPreview: '#08140F' },
  { id: 'graphite', label: 'Graphite Orange', accent: '#F97316', bgPreview: '#0E0E10' },
  { id: 'blue', label: 'Professional Blue', accent: '#2563EB', bgPreview: '#121826' },
  { id: 'security', label: 'Security Green', accent: '#22C55E', bgPreview: '#0F1412' },
];

export const LANGUAGE_OPTIONS = [
  { label: 'Auto-detect', value: 'auto' },
  { label: 'FR', value: 'fr' },
  { label: 'AR', value: 'ar' },
  { label: 'EN', value: 'en' },
];

export const THEME_VARIABLES: Record<ThemePreset['id'], ThemeVariableSet> = {
  teal: {
    light: {
      '--bg-base': '#F3F4F6',
      '--bg-surface': '#FFFFFF',
      '--bg-surface-2': '#F9FAFB',
      '--bg-surface-3': '#E5E7EB',
      '--bg-surface-4': '#D1D5DB',
      '--border': '#E5E7EB',
      '--accent': '#0F766E',
      '--accent-hover': '#0D9488',
      '--accent-subtle': '#0F766E12',
      '--accent-border': '#0F766E2B',
      '--interaction': '#0D9488',
      '--interaction-hover': '#0F766E',
      '--text-primary': '#111827',
      '--text-secondary': '#6B7280',
      '--text-muted': '#9CA3AF',
    },
    dark: {
      '--bg-base': '#080E1A',
      '--bg-surface': '#111827',
      '--bg-surface-2': '#1F2937',
      '--bg-surface-3': '#374151',
      '--bg-surface-4': '#4B5563',
      '--border': '#374151',
      '--accent': '#14B8A6',
      '--accent-hover': '#2DD4BF',
      '--accent-subtle': '#14B8A616',
      '--accent-border': '#14B8A632',
      '--interaction': '#14B8A6',
      '--interaction-hover': '#2DD4BF',
      '--text-primary': '#F9FAFB',
      '--text-secondary': '#9CA3AF',
      '--text-muted': '#4B5563',
    },
  },
  cyan: {
    light: {
      '--bg-base': '#F3F6F8',
      '--bg-surface': '#FFFFFF',
      '--bg-surface-2': '#F8FAFB',
      '--bg-surface-3': '#E2E8F0',
      '--bg-surface-4': '#CBD5E1',
      '--border': '#E2E8F0',
      '--accent': '#0891B2',
      '--accent-hover': '#0E7490',
      '--accent-subtle': '#0891B210',
      '--accent-border': '#0891B226',
      '--interaction': '#0891B2',
      '--interaction-hover': '#0E7490',
      '--text-primary': '#0F172A',
      '--text-secondary': '#64748B',
      '--text-muted': '#94A3B8',
    },
    dark: {
      '--bg-base': '#081217',
      '--bg-surface': '#0F1D26',
      '--bg-surface-2': '#1A2E3A',
      '--bg-surface-3': '#2A4050',
      '--bg-surface-4': '#3B5468',
      '--border': '#2A4050',
      '--accent': '#06B6D4',
      '--accent-hover': '#22D3EE',
      '--accent-subtle': '#06B6D414',
      '--accent-border': '#06B6D430',
      '--interaction': '#06B6D4',
      '--interaction-hover': '#22D3EE',
      '--text-primary': '#F1F5F9',
      '--text-secondary': '#94A3B8',
      '--text-muted': '#3B5468',
    },
  },
  rose: {
    light: {
      '--bg-base': '#F6F3F5',
      '--bg-surface': '#FFFFFF',
      '--bg-surface-2': '#FBF8FA',
      '--bg-surface-3': '#F0E4EB',
      '--bg-surface-4': '#E0CED8',
      '--border': '#F0E4EB',
      '--accent': '#DB2777',
      '--accent-hover': '#BE185D',
      '--accent-subtle': '#DB277710',
      '--accent-border': '#DB277726',
      '--interaction': '#DB2777',
      '--interaction-hover': '#BE185D',
      '--text-primary': '#1C1017',
      '--text-secondary': '#78606C',
      '--text-muted': '#A08894',
    },
    dark: {
      '--bg-base': '#120A10',
      '--bg-surface': '#1D1220',
      '--bg-surface-2': '#2D1E30',
      '--bg-surface-3': '#402C44',
      '--bg-surface-4': '#553D58',
      '--border': '#402C44',
      '--accent': '#EC4899',
      '--accent-hover': '#F472B6',
      '--accent-subtle': '#EC489914',
      '--accent-border': '#EC489930',
      '--interaction': '#EC4899',
      '--interaction-hover': '#F472B6',
      '--text-primary': '#FAF5F8',
      '--text-secondary': '#A08894',
      '--text-muted': '#553D58',
    },
  },
  indigo: {
  light: {
    '--bg-base': '#F7F8FF',
    '--bg-surface': '#FFFFFF',
    '--bg-surface-2': '#F1F5F9',
    '--bg-surface-3': '#E5E7EB',
    '--bg-surface-4': '#D1D5DB',
    '--border': '#E5E7EB',

    '--accent': '#6366F1',
    '--accent-hover': '#818CF8',
    '--accent-subtle': '#6366F112',
    '--accent-border': '#6366F12B',

    '--interaction': '#6366F1',
    '--interaction-hover': '#818CF8',

    '--text-primary': '#111827',
    '--text-secondary': '#6B7280',
    '--text-muted': '#9CA3AF',
  },
  dark: {
    '--bg-base': '#0F1220',
    '--bg-surface': '#151933',
    '--bg-surface-2': '#1F2547',
    '--bg-surface-3': '#2B3160',
    '--bg-surface-4': '#3A417A',
    '--border': '#2B3160',

    '--accent': '#6366F1',
    '--accent-hover': '#818CF8',
    '--accent-subtle': '#6366F114',
    '--accent-border': '#6366F130',

    '--interaction': '#6366F1',
    '--interaction-hover': '#818CF8',

    '--text-primary': '#F8FAFC',
    '--text-secondary': '#94A3B8',
    '--text-muted': '#3A417A',
  },
  },
  emerald: {
    light: {
      '--bg-base': '#F4FBF7',
      '--bg-surface': '#FFFFFF',
      '--bg-surface-2': '#F0FDF4',
      '--bg-surface-3': '#DCFCE7',
      '--bg-surface-4': '#BBF7D0',
      '--border': '#DCFCE7',

      '--accent': '#059669',
      '--accent-hover': '#10B981',
      '--accent-subtle': '#05966912',
      '--accent-border': '#0596692B',

      '--interaction': '#059669',
      '--interaction-hover': '#10B981',

      '--text-primary': '#052E1B',
      '--text-secondary': '#166534',
      '--text-muted': '#4D7C6F',
    },
    dark: {
      '--bg-base': '#08140F',
      '--bg-surface': '#0F1F17',
      '--bg-surface-2': '#173027',
      '--bg-surface-3': '#214438',
      '--bg-surface-4': '#2C5A4C',
      '--border': '#214438',

      '--accent': '#10B981',
      '--accent-hover': '#34D399',
      '--accent-subtle': '#10B98116',
      '--accent-border': '#10B98132',

      '--interaction': '#10B981',
      '--interaction-hover': '#34D399',

      '--text-primary': '#ECFDF5',
      '--text-secondary': '#A7F3D0',
      '--text-muted': '#2C5A4C',
    }
  },
  graphite: {
    light: {
      '--bg-base': '#F7F7F8',
      '--bg-surface': '#FFFFFF',
      '--bg-surface-2': '#FAFAFA',
      '--bg-surface-3': '#E5E5E5',
      '--bg-surface-4': '#D4D4D4',
      '--border': '#E5E5E5',

      '--accent': '#EA580C',
      '--accent-hover': '#F97316',
      '--accent-subtle': '#EA580C12',
      '--accent-border': '#EA580C2B',

      '--interaction': '#EA580C',
      '--interaction-hover': '#F97316',

      '--text-primary': '#18181B',
      '--text-secondary': '#52525B',
      '--text-muted': '#A1A1AA',
    },
    dark: {
      '--bg-base': '#0E0E10',
      '--bg-surface': '#16161A',
      '--bg-surface-2': '#1F1F24',
      '--bg-surface-3': '#2A2A31',
      '--bg-surface-4': '#35353D',
      '--border': '#2A2A31',

      '--accent': '#F97316',
      '--accent-hover': '#FB923C',
      '--accent-subtle': '#F9731616',
      '--accent-border': '#F9731632',

      '--interaction': '#F97316',
      '--interaction-hover': '#FB923C',

      '--text-primary': '#FAFAFA',
      '--text-secondary': '#A1A1AA',
      '--text-muted': '#52525B',
    }
  },
  blue: {
  light: {
    '--bg-base': '#F4F6F9',
    '--bg-surface': '#FFFFFF',
    '--bg-surface-2': '#F8FAFC',
    '--bg-surface-3': '#E9EEF5',
    '--bg-surface-4': '#DCE3EC',
    '--border': '#DEE2E6',

    '--accent': '#2563EB',
    '--accent-hover': '#1D4ED8',
    '--accent-subtle': '#2563EB12',
    '--accent-border': '#2563EB2B',

    '--interaction': '#2563EB',
    '--interaction-hover': '#1D4ED8',

    '--text-primary': '#212529',
    '--text-secondary': '#6C757D',
    '--text-muted': '#9CA3AF',
  },
  dark: {
    '--bg-base': '#121826',
    '--bg-surface': '#1E1E1E',
    '--bg-surface-2': '#2D2D2D',
    '--bg-surface-3': '#383838',
    '--bg-surface-4': '#444444',
    '--border': '#30363D',

    '--accent': '#3B82F6',
    '--accent-hover': '#60A5FA',
    '--accent-subtle': '#3B82F614',
    '--accent-border': '#3B82F630',

    '--interaction': '#3B82F6',
    '--interaction-hover': '#60A5FA',

    '--text-primary': '#E1E1E1',
    '--text-secondary': '#8B949E',
    '--text-muted': '#555555',
  },
  },
  security: {
  light: {
    '--bg-base': '#F6FAF7',
    '--bg-surface': '#FFFFFF',
    '--bg-surface-2': '#F0FDF4',
    '--bg-surface-3': '#DCFCE7',
    '--bg-surface-4': '#BBF7D0',
    '--border': '#DCFCE7',

    '--accent': '#16A34A',
    '--accent-hover': '#22C55E',
    '--accent-subtle': '#16A34A12',
    '--accent-border': '#16A34A2B',

    '--interaction': '#16A34A',
    '--interaction-hover': '#22C55E',

    '--text-primary': '#1F2937',
    '--text-secondary': '#6B7280',
    '--text-muted': '#94A3B8',
  },
  dark: {
    '--bg-base': '#0F1412',
    '--bg-surface': '#161B18',
    '--bg-surface-2': '#1F2622',
    '--bg-surface-3': '#29332E',
    '--bg-surface-4': '#33403A',
    '--border': '#29332E',

    '--accent': '#22C55E',
    '--accent-hover': '#4ADE80',
    '--accent-subtle': '#22C55E14',
    '--accent-border': '#22C55E30',

    '--interaction': '#22C55E',
    '--interaction-hover': '#4ADE80',

    '--text-primary': '#ECFDF5',
    '--text-secondary': '#A7F3D0',
    '--text-muted': '#3F4F47',
  },
  },
};

export const DEFAULT_SETTINGS = {
  appearance: {
    selectedThemeId: 'teal' as ThemePreset['id'],
    darkMode: true,
  },
  retention: {
    messagesLogDays: 30,
    blockedMessagesDays: 90,
    alertHistoryDays: 180,
    riskProfileHistoryDays: 60,
  } as RetentionSettings,
  notifications: {
    emailNotifications: true,
    inAppNotifications: true,
    notifyOnBlock: true,
    notifyOnEscalate: true,
    notifyOnWarn: false,
    quietHoursStart: '23:00',
    quietHoursEnd: '07:00',
  } as NotificationDefaults,
  moderation: {
    defaultLanguage: 'auto',
    autoResolveAllow: true,
    rateLimitThreshold: 50,
    parentPortalAccess: true,
  } as ModerationDefaults,
  adminAccount: {
    displayName: 'Aegis Administrator',
    email: 'admin@aegisai.local',
    lastLogin: 'Today at 09:14 - 192.168.1.1',
  } as AdminAccountSettings,
};
