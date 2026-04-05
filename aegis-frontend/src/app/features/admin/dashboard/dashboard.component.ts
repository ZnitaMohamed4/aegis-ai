import { Component, signal, OnInit, OnDestroy } from '@angular/core';
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

  getRiskBarWidth(score: number): string {
    return `${score * 100}%`;
  }
}
