import { Component, signal, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ChartModule } from 'primeng/chart';
import { getRiskHex, getDecisionClass } from '@shared/utils/severity.utils';
import {
  MOCK_STATS, MOCK_RECENT_ALERTS, MOCK_AT_RISK_CHILDREN,
  HARASSMENT_CHART_DATA, HARASSMENT_CHART_OPTIONS,
  WEEKLY_CHART_DATA, WEEKLY_CHART_OPTIONS,
  HOURLY_CHART_DATA, HOURLY_CHART_OPTIONS,
  LANGUAGE_CHART_DATA, LANGUAGE_CHART_OPTIONS,
  FeedEvent, getNextFeedEvent
} from './dashboard.data';
import { ApiService } from '@core/services/api.service';
import { AlertService, WebSocketAlertPayload } from '@core/services/alert.service';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, ChartModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class DashboardComponent implements OnInit, OnDestroy {
  stats = MOCK_STATS;
  recentAlerts = MOCK_RECENT_ALERTS;
  atRiskChildren = MOCK_AT_RISK_CHILDREN;
  harassmentChartData = HARASSMENT_CHART_DATA;
  harassmentChartOptions = HARASSMENT_CHART_OPTIONS;
  weeklyChartData = WEEKLY_CHART_DATA;
  weeklyChartOptions = WEEKLY_CHART_OPTIONS;
  hourlyChartData = HOURLY_CHART_DATA;
  hourlyChartOptions = HOURLY_CHART_OPTIONS;
  languageChartData = LANGUAGE_CHART_DATA;
  languageChartOptions = LANGUAGE_CHART_OPTIONS;

  getRiskHex = getRiskHex;
  getDecisionClass = getDecisionClass;

  // Live activity feed
  feedEvents = signal<FeedEvent[]>([]);
  private feedCounter = 0;
  private feedInterval: ReturnType<typeof setInterval> | null = null;
  private readonly MAX_FEED = 20;

  // 1. INJECT THE WEBSOCKET SERVICE (Modern Angular v16+)
  private alertService = inject(AlertService);
  private alertSub?: Subscription;

  // 2. Inject the new API Service
  private apiService = inject(ApiService);

  ngOnInit() {
    // Seed with 5 initial events
    for (let i = 0; i < 5; i++) {
      this.feedCounter++;
      this.feedEvents.update(list => [getNextFeedEvent(this.feedCounter), ...list]);
    }
    // Add a new event every 6 seconds
    this.feedInterval = setInterval(() => {
      this.feedCounter++;
      this.feedEvents.update(list => {
        const next = [getNextFeedEvent(this.feedCounter), ...list];
        return next.slice(0, this.MAX_FEED);
      });
    }, 6000);

    // 2. SUBSCRIBE TO THE WEBSOCKET LOUDSPEAKER
    this.alertSub = this.alertService.alerts$.subscribe((alert: WebSocketAlertPayload) => {
      // Map the incoming Django AI payload to the frontend Feed Event
      const newEvent: FeedEvent = {
        id: alert.id,
        time: new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        type: alert.decision as any, // e.g., 'block', 'escalate', 'allow'
        icon: alert.decision === 'escalate' || alert.decision === 'block' ? 'pi-exclamation-triangle' : 'pi-shield',
        text: `[${alert.primary_class.toUpperCase()}] detected with ${Math.round(alert.m1_score * 100)}% severity from ${alert.sender.substring(0, 8)}...`
      };

      // 3. UPDATE THE SIGNAL (Instantly repaints the screen)
      this.feedEvents.update(list => {
        const next = [newEvent, ...list];
        return next.slice(0, this.MAX_FEED);
      });
    });
      // 4. FETCH REAL LIVE STATS FROM POSTGRESQL
      this.apiService.getDashboardStats().subscribe({
        next: (data) => {
          console.log('[AEGIS] ✅ Dashboard Stats Loaded:', data);
          
          // Here we update our dashboard properties with real data!
          // We map the backend stats to the "MOCK_STATS" structure so the UI updates
          this.stats = [
            {
              label: 'Avg Latency',
              value: data.stats.avg_latency_ms + 'ms',
              icon: 'pi-gauge',
              trend: 'stable',
              trendUp: true,
              color: 'info'
            },
            {
              label: 'Total Alerts Today',
              value: data.stats.total_alerts_today,
              icon: 'pi-bell',
              trend: 'Live from DB',
              trendUp: true,
              color: 'critical'
            },
            {
              label: 'Messages Blocked',
              value: data.stats.total_blocked_today,
              icon: 'pi-ban',
              trend: 'Live from DB',
              trendUp: true,
              color: 'high'
            },
            {
              label: 'Pending Review',
              value: data.stats.pending_review,
              icon: 'pi-clock',
              trend: 'Grey Zone',
              trendUp: false,
              color: 'medium'
            }
          ];

          // Update the at-risk children table too!
          this.atRiskChildren = data.at_risk_users.map(user => ({
            id: user.id,
            name: user.whatsapp.split('@')[0], // Show number instead of name for now
            whatsapp: user.whatsapp,
            risk_score: user.risk_score,
            risk_level: user.risk_level.toLowerCase(),
            blocked_today: user.blocked_total,
            last_incident: 'Recently'
          }));
        },
        error: (err) => console.error('[AEGIS] ❌ Failed to load stats:', err)
      });
  }

  ngOnDestroy() {
    if (this.feedInterval) clearInterval(this.feedInterval);
    // Always clean up your subscriptions to prevent memory leaks!
    if (this.alertSub) this.alertSub.unsubscribe();
  }

  getFeedColor(type: string): string {
    const map: Record<string, string> = {
      block: 'var(--critical)',
      escalate: 'var(--high)',
      warn: 'var(--medium)',
      allow: 'var(--low)',
      review: 'var(--accent)',
      risk: 'var(--high)'
    };
    return map[type] ?? 'var(--text-muted)';
  }

  getRiskBarWidth(score: number): string {
    return `${score * 100}%`;
  }
}
