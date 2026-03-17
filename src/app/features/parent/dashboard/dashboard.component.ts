import { Component, signal, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ChartModule } from 'primeng/chart';
import { getRiskHex, getDecisionClass } from '@shared/utils/severity.utils';
import {
  MOCK_RECENT_ALERTS, 
  HARASSMENT_CHART_DATA, HARASSMENT_CHART_OPTIONS,
  WEEKLY_CHART_DATA, WEEKLY_CHART_OPTIONS,
  FeedEvent, getNextFeedEvent
} from '@features/admin/dashboard/dashboard.data';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, ChartModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class DashboardComponent implements OnInit, OnDestroy {
  // Parent-specific stats
  stats = [
    { label: 'Messages Monitored', value: '1,204', trend: '+12%', trendUp: true, icon: 'pi-comments', color: 'accent' },
    { label: 'Threats Blocked', value: '14', trend: '-2', trendUp: true, icon: 'pi-shield', color: 'low' },
    { label: 'Active Alerts', value: '3', trend: '+1', trendUp: false, icon: 'pi-bell', color: 'critical' },
    { label: 'Current Risk Level', value: 'Low', trend: 'Stable', trendUp: true, icon: 'pi-chart-line', color: 'low' }
  ];

  recentAlerts = MOCK_RECENT_ALERTS.slice(0, 4);
  harassmentChartData = HARASSMENT_CHART_DATA;
  harassmentChartOptions = HARASSMENT_CHART_OPTIONS;
  weeklyChartData = WEEKLY_CHART_DATA;
  weeklyChartOptions = WEEKLY_CHART_OPTIONS;

  getRiskHex = getRiskHex;
  getDecisionClass = getDecisionClass;

  // Live activity feed simulation
  feedEvents = signal<FeedEvent[]>([]);
  private feedCounter = 0;
  private feedInterval: any;
  private readonly MAX_FEED = 15;

  ngOnInit() {
    for (let i = 0; i < 3; i++) {
      this.feedCounter++;
      this.feedEvents.update(list => [getNextFeedEvent(this.feedCounter), ...list]);
    }
    this.feedInterval = setInterval(() => {
      this.feedCounter++;
      this.feedEvents.update(list => {
        const next = [getNextFeedEvent(this.feedCounter), ...list];
        return next.slice(0, this.MAX_FEED);
      });
    }, 8000);
  }

  ngOnDestroy() {
    if (this.feedInterval) clearInterval(this.feedInterval);
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
}
