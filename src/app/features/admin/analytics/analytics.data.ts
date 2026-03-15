export interface Harasser {
  contact: string;
  name?: string;
  messagesBlocked: number;
  threatLevel: string;
}

export interface ChildRisk {
  name: string;
  previousScore: number;
  currentScore: number;
  trend: string;
}

// 30 days of data
const labels30d = Array.from({ length: 30 }, (_, i) => {
  const d = new Date();
  d.setDate(d.getDate() - (29 - i));
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
});

export const ANALYTICS_DATA = {
  labels: labels30d,
  
  // Risk Score Evolution (Line)
  riskScores: Array.from({ length: 30 }, () => 0.2 + Math.random() * 0.5),

  // Decisions Trend (Area/Stacked Bar) - Blocked, Warned, Allowed
  decisions: {
    blocked: Array.from({ length: 30 }, () => Math.floor(Math.random() * 20) + 5),
    warned: Array.from({ length: 30 }, () => Math.floor(Math.random() * 15) + 2),
    allowed: Array.from({ length: 30 }, () => Math.floor(Math.random() * 200) + 50)
  },

  // Category Breakdown (Stacked Bar)
  categories: {
    verbal: Array.from({ length: 30 }, () => Math.floor(Math.random() * 10) + 2),
    threat: Array.from({ length: 30 }, () => Math.floor(Math.random() * 5)),
    sexual: Array.from({ length: 30 }, () => Math.floor(Math.random() * 3)),
    discrimination: Array.from({ length: 30 }, () => Math.floor(Math.random() * 4))
  },

  // Pipeline Latency (Line)
  latency: Array.from({ length: 30 }, () => Math.floor(100 + Math.random() * 150)),

  // False Positive Rate Trend (Percentage) - Convert to number series for chart making
  falsePositives: Array.from({ length: 30 }, () => parseFloat((Math.random() * 5 + 1).toFixed(1))),

  // Critique vs Block ratio
  critiqueVsBlock: Array.from({ length: 30 }, () => 0.5 + Math.random() * 0.3),

  // --- NEW CHARTS MOCK DATA ---
  
  // 1. Confidence Score Distribution (Histogram)
  // Bins: [0-0.5, 0.5-0.65, 0.65-0.75 (Grey Zone), 0.75-0.85, 0.85-1.0]
  confidenceDistribution: {
    labels: ['< 0.50 (Safe)', '0.50 - 0.65', '0.65 - 0.75 (Grey Zone)', '0.75 - 0.85', '> 0.85 (Critical)'],
    data: [12000, 3500, 1800, 2100, 4300]
  },

  // 2. Agent 3 Activation Rate (Percentage over time)
  agent3Activation: Array.from({ length: 30 }, () => parseFloat((Math.random() * 10 + 15).toFixed(1))),

  // 3. Peak Activity Heatmap (Days x Hours - 7x24, mocked with random weights)
  // We'll generate a grid of objects later. Let's just create an easy structure.
  // Higher weights after school (16-22)
  peakActivity: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => {
    return Array.from({ length: 24 }, (_, hour) => {
      // higher probability of higher value at 16-22 hours
      let base = Math.random() * 20;
      if (hour >= 16 && hour <= 22) base += Math.random() * 50 + 20;
      if (hour >= 0 && hour <= 6) base = Math.random() * 5; // sleep
      return Math.floor(base);
    });
  }),

  // 4. Review Queue Metrics
  reviewQueue: {
    avgResolutionTime: '3m 42s',
    decisions: [420, 180] // Block (Override to Block or kept block), Allow (False positive override)
  },

  // Static distribution data
  languageDistribution: [1200, 300, 150], // FR, AR, EN
  notificationStats: [450, 120, 800, 15], // SMS, EMAIL, PUSH, APPEL

  // Tables
  topHarassers: [
    { contact: '+33 6 12 34 56 78', name: 'Unknown', messagesBlocked: 45, threatLevel: 'critical' },
    { contact: '+33 6 98 76 54 32', name: 'Alex M.', messagesBlocked: 23, threatLevel: 'high' },
    { contact: '+33 7 11 22 33 44', name: 'Unknown', messagesBlocked: 18, threatLevel: 'high' },
    { contact: '+33 6 55 44 33 22', name: 'Jordan', messagesBlocked: 12, threatLevel: 'medium' }
  ] as Harasser[],

  perChildRisk: [
    { name: 'Lucas P.', previousScore: 0.35, currentScore: 0.82, trend: '+0.47' },
    { name: 'Emma M.', previousScore: 0.15, currentScore: 0.55, trend: '+0.40' },
    { name: 'Hugo D.', previousScore: 0.60, currentScore: 0.85, trend: '+0.25' },
    { name: 'Chloé L.', previousScore: 0.20, currentScore: 0.35, trend: '+0.15' }
  ] as ChildRisk[]
};
