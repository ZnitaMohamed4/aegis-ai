export interface StatCard {
  label: string;
  value: string | number;
  icon: string;
  trend: string;
  trendUp: boolean;
  color: string;
}

export interface RecentAlert {
  id: string;
  preview: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  category: string;
  time: string;
  decision: string;
}

export interface AtRiskChild {
  id: string;
  name: string;
  whatsapp: string;
  risk_score: number;
  risk_level: string;
  blocked_today: number;
  last_incident: string;
}

export const MOCK_STATS: StatCard[] = [
  {
    label: 'Total Alerts Today',
    value: 24,
    icon: 'pi-bell',
    trend: '+12% vs yesterday',
    trendUp: true,
    color: 'critical'
  },
  {
    label: 'Messages Blocked',
    value: 138,
    icon: 'pi-ban',
    trend: '+5% vs yesterday',
    trendUp: true,
    color: 'high'
  },
  {
    label: 'Pending Review',
    value: 7,
    icon: 'pi-clock',
    trend: '3 urgent',
    trendUp: false,
    color: 'medium'
  },
  {
    label: 'Active Children',
    value: 42,
    icon: 'pi-users',
    trend: '2 high risk',
    trendUp: false,
    color: 'accent'
  }
];

export const MOCK_RECENT_ALERTS: RecentAlert[] = [
  {
    id: '1',
    preview: 'Je vais te retrouver après...',
    severity: 'critical',
    category: 'Threat',
    time: '2 min ago',
    decision: 'BLOCK'
  },
  {
    id: '2',
    preview: 'T\'es vraiment nul, personne...',
    severity: 'high',
    category: 'Verbal Harassment',
    time: '15 min ago',
    decision: 'BLOCK'
  },
  {
    id: '3',
    preview: 'Envoie moi tes photos sinon...',
    severity: 'critical',
    category: 'Sexual Harassment',
    time: '34 min ago',
    decision: 'ESCALATE'
  },
  {
    id: '4',
    preview: 'Les gens comme toi ne méritent...',
    severity: 'medium',
    category: 'Discrimination',
    time: '1 hr ago',
    decision: 'WARN'
  },
  {
    id: '5',
    preview: 'Haha t\'as vu sa tête sur la...',
    severity: 'medium',
    category: 'Verbal Harassment',
    time: '2 hr ago',
    decision: 'WARN'
  }
];

export const MOCK_AT_RISK_CHILDREN: AtRiskChild[] = [
  {
    id: '1',
    name: 'Adam B.',
    whatsapp: '+212 6XX XXX X01',
    risk_score: 0.91,
    risk_level: 'critical',
    blocked_today: 5,
    last_incident: '2 min ago'
  },
  {
    id: '2',
    name: 'Sara M.',
    whatsapp: '+212 6XX XXX X02',
    risk_score: 0.74,
    risk_level: 'high',
    blocked_today: 3,
    last_incident: '1 hr ago'
  },
  {
    id: '3',
    name: 'Youssef K.',
    whatsapp: '+212 6XX XXX X03',
    risk_score: 0.61,
    risk_level: 'medium',
    blocked_today: 1,
    last_incident: '3 hr ago'
  },
  {
    id: '4',
    name: 'Nadia R.',
    whatsapp: '+212 6XX XXX X04',
    risk_score: 0.58,
    risk_level: 'medium',
    blocked_today: 1,
    last_incident: '5 hr ago'
  }
];

export const HARASSMENT_CHART_DATA = {
  labels: ['Verbal', 'Threat', 'Sexual', 'Discrimination', 'Safe'],
  datasets: [
    {
      data: [38, 22, 18, 14, 8],
      backgroundColor: [
        '#FF7A30',
        '#FF4D4D',
        '#A78BFA',
        '#4F7FFF',
        '#10D9A0'
      ],
      borderWidth: 0,
      hoverOffset: 6
    }
  ]
};

export const HARASSMENT_CHART_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom',
      labels: {
        color: '#94A3B8',
        padding: 16,
        font: { size: 12 }
      }
    }
  },
  cutout: '70%'
};

export const WEEKLY_CHART_DATA = {
  labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
  datasets: [
    {
      label: 'Blocked',
      data: [18, 24, 31, 19, 27, 14, 9],
      backgroundColor: 'rgba(255,77,77,0.75)',
      borderColor: '#FF4D4D',
      borderWidth: 1,
      borderRadius: 4,
    },
    {
      label: 'Warned',
      data: [11, 15, 22, 13, 18, 8, 5],
      backgroundColor: 'rgba(255,176,32,0.65)',
      borderColor: '#FFB020',
      borderWidth: 1,
      borderRadius: 4,
    }
  ]
};

export const WEEKLY_CHART_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: {
        color: '#94A3B8',
        padding: 16,
        font: { size: 12 }
      }
    }
  },
  scales: {
    x: {
      grid: { color: 'rgba(148,163,184,0.1)' },
      ticks: { color: '#94A3B8', font: { size: 12 } }
    },
    y: {
      grid: { color: 'rgba(148,163,184,0.1)' },
      ticks: { color: '#94A3B8', font: { size: 12 } },
      beginAtZero: true
    }
  }
};

// ── Hourly Threat Detection Chart ────────────────────
export const HOURLY_CHART_DATA = {
  labels: [
    '00h', '02h', '04h', '06h', '08h', '10h',
    '12h', '14h', '16h', '18h', '20h', '22h'
  ],
  datasets: [
    {
      label: 'Threats',
      data: [2, 1, 0, 1, 5, 9, 14, 18, 22, 16, 11, 6],
      fill: true,
      backgroundColor: 'rgba(255,77,77,0.12)',
      borderColor: '#FF4D4D',
      borderWidth: 2,
      tension: 0.35,
      pointRadius: 3,
      pointBackgroundColor: '#FF4D4D',
    },
    {
      label: 'Safe',
      data: [8, 4, 2, 6, 28, 45, 52, 61, 58, 44, 32, 14],
      fill: true,
      backgroundColor: 'rgba(16,217,160,0.08)',
      borderColor: '#10D9A0',
      borderWidth: 2,
      tension: 0.35,
      pointRadius: 3,
      pointBackgroundColor: '#10D9A0',
    }
  ]
};

export const HOURLY_CHART_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: {
        color: '#94A3B8',
        padding: 16,
        font: { size: 12 }
      }
    }
  },
  scales: {
    x: {
      grid: { color: 'rgba(148,163,184,0.1)' },
      ticks: { color: '#94A3B8', font: { size: 11 } }
    },
    y: {
      grid: { color: 'rgba(148,163,184,0.1)' },
      ticks: { color: '#94A3B8', font: { size: 11 } },
      beginAtZero: true
    }
  }
};

// ── Live Activity Feed ──────────────────────────────
export type FeedEventType = 'block' | 'escalate' | 'warn' | 'allow' | 'review' | 'risk';

export interface FeedEvent {
  id: number;
  time: string;
  type: FeedEventType;
  icon: string;
  text: string;
}

const FEED_POOL: Omit<FeedEvent, 'id' | 'time'>[] = [
  { type: 'block', icon: 'pi-ban', text: 'Message blocked for Child #A1 — Threat detected (0.94)' },
  { type: 'escalate', icon: 'pi-arrow-up-right', text: 'Escalation alert: +212 6XX XX03 → Child #B2' },
  { type: 'block', icon: 'pi-ban', text: 'Message blocked for Child #C3 — Sexual harassment (0.88)' },
  { type: 'warn', icon: 'pi-exclamation-triangle', text: 'Warning issued to +212 6XX XX07 — Verbal harassment' },
  { type: 'review', icon: 'pi-clock', text: 'New grey-zone message queued for review (confidence: 0.69)' },
  { type: 'risk', icon: 'pi-shield', text: 'Risk score updated: Child #A1 → 0.91 (critical)' },
  { type: 'allow', icon: 'pi-check', text: 'Message allowed for Child #D4 — Safe (0.12)' },
  { type: 'block', icon: 'pi-ban', text: 'Message blocked for Child #B2 — Discrimination (0.82)' },
  { type: 'escalate', icon: 'pi-arrow-up-right', text: 'Repeated targeting detected: +212 6XX XX05 → 3 children' },
  { type: 'warn', icon: 'pi-exclamation-triangle', text: 'Warning issued to +212 6XX XX11 — Bullying pattern' },
  { type: 'review', icon: 'pi-clock', text: 'Grey-zone message queued — LLM confidence 0.71' },
  { type: 'block', icon: 'pi-ban', text: 'Message blocked for Child #E5 — Threat (0.91)' },
  { type: 'risk', icon: 'pi-shield', text: 'Risk score updated: Child #C3 → 0.74 (high)' },
  { type: 'allow', icon: 'pi-check', text: 'Message allowed for Child #A1 — Safe (0.08)' },
  { type: 'escalate', icon: 'pi-arrow-up-right', text: 'Night activity spike: +212 6XX XX03 (82% after midnight)' },
];

export function getNextFeedEvent(counter: number): FeedEvent {
  const entry = FEED_POOL[counter % FEED_POOL.length];
  const now = new Date();
  return {
    id: counter,
    time: now.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
    ...entry
  };
}
