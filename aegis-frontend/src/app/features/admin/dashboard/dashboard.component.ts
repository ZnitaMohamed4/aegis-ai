import { Component, signal, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ChartModule } from 'primeng/chart';
import { SkeletonModule } from 'primeng/skeleton';
import { getRiskHex, getDecisionClass } from '@shared/utils/severity.utils';
import {
  HARASSMENT_CHART_OPTIONS,
  WEEKLY_CHART_OPTIONS,
  HOURLY_CHART_OPTIONS,
  LANGUAGE_CHART_OPTIONS,
  FeedEvent
} from './dashboard.data';
import { ApiService } from '@core/services/api.service';
import { AlertService, WebSocketAlertPayload } from '@core/services/alert.service';
import { Subscription } from 'rxjs';
import { ChangeDetectorRef } from '@angular/core';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, ChartModule, SkeletonModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class DashboardComponent implements OnInit, OnDestroy {
  stats: any[] | null = null;
  recentAlerts: any[] | null = null;
  atRiskChildren: any[] | null = null;
  
  harassmentChartData: any = null;
  harassmentChartOptions = HARASSMENT_CHART_OPTIONS;
  weeklyChartData: any = null;
  weeklyChartOptions = WEEKLY_CHART_OPTIONS;
  hourlyChartData: any = null;
  hourlyChartOptions = HOURLY_CHART_OPTIONS;
  languageChartData: any = null;
  languageChartOptions = LANGUAGE_CHART_OPTIONS;

  getRiskHex = getRiskHex;
  getDecisionClass = getDecisionClass;

  // Live activity feed
  feedEvents = signal<FeedEvent[]>([]);
  private readonly MAX_FEED = 20;

  private alertService = inject(AlertService);
  private alertSub?: Subscription;
  private apiService = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);

  ngOnInit() {
    // Subscribe to WebSockets for Live Alerts
    this.alertSub = this.alertService.alerts$.subscribe((alert: WebSocketAlertPayload) => {
      let feedText = '';
      let feedIcon = 'pi-info-circle';
      let cleanText = (alert.text || "(Media/Sticker)").substring(0, 50) + "...";
      let shortSender = alert.sender.split('@')[0];
      
      if (alert.llm_triggered) {
        feedText = `🧠 Agent 3 (LLM) forced [${alert.decision.toUpperCase()}] for ${shortSender}. Reason: "${alert.llm_explanation}"`;
        feedIcon = 'pi-bolt';
      } else {
        switch(alert.decision.toUpperCase()) {
          case 'ALLOW':
            feedText = `Processed safely in background: "${cleanText}"`;
            feedIcon = 'pi-verified';
            break;
          case 'WARN':
            feedText = `Issued automated warning for [${(alert.primary_class || '').toUpperCase()}] on ${shortSender}`;
            feedIcon = 'pi-exclamation-triangle';
            break;
          case 'BLOCK':
          case 'ESCALATE':
            feedText = `ACTIVE SHIELD 🛡️ Blocked [${(alert.primary_class || '').toUpperCase()}] with ${Math.round(alert.m1_score * 100)}% severity!`;
            feedIcon = 'pi-ban';
            break;
          default:
            feedText = `Analyzed new incoming stream payload...`;
        }
      }

      const newEvent: FeedEvent = {
        id: alert.id,
        time: new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        type: alert.decision.toLowerCase() as any,
        icon: feedIcon,
        text: feedText
      };

      this.feedEvents.update(list => {
        const next = [newEvent, ...list];
        return next.slice(0, this.MAX_FEED);
      });
      
      // Only inject HARMFUL things into recentAlerts
      if (this.recentAlerts && alert.type === 'alert') {
        this.recentAlerts = [{
          id: alert.id,
          preview: alert.text.length > 50 ? alert.text.substring(0, 50) + "..." : alert.text,
          severity: alert.severity,
          category: alert.primary_class,
          time: 'Just now',
          decision: alert.decision.toUpperCase()
        }, ...this.recentAlerts].slice(0, 5);
      }

      // Update Live Stat Cards dynamically!
      if (this.stats) {
        // 1. Always increment 'Total Alerts Today'
        this.stats[1].value = Number(this.stats[1].value) + 1;
        
        // 2. Increment 'Messages Blocked' if it's a block/escalate
        if (alert.decision.toUpperCase() === 'BLOCK' || alert.decision.toUpperCase() === 'ESCALATE') {
          this.stats[2].value = Number(this.stats[2].value) + 1;
        }

        // 3. Increment 'Agent 3 Interventions' if LLM intervened
        if (alert.llm_triggered) {
          this.stats[3].value = Number(this.stats[3].value) + 1;
        }
      }

      // Update Donut Chart dynamically!
      if (this.harassmentChartData && alert.primary_class && alert.primary_class !== 'safe') {
        const newData = [...this.harassmentChartData.datasets[0].data];
        
        switch (alert.primary_class.toLowerCase()) {
          case 'verbal_harassment': newData[0]++; break;
          case 'threat': newData[1]++; break;
          case 'sexual_harassment': newData[2]++; break;
          case 'discrimination': newData[3]++; break;
        }

        this.harassmentChartData = {
          ...this.harassmentChartData,
          datasets: [{
            ...this.harassmentChartData.datasets[0],
            data: newData
          }]
        };
      }

      // Update Weekly Bar Chart dynamically! (Adding to today's bar)
      if (this.weeklyChartData) {
        const blockedData = [...this.weeklyChartData.datasets[0].data];
        const warnedData = [...this.weeklyChartData.datasets[1].data];
        const lastIdx = blockedData.length - 1; // Today is the last entry
        
        if (alert.decision.toUpperCase() === 'BLOCK' || alert.decision.toUpperCase() === 'ESCALATE') {
          blockedData[lastIdx]++;
        } else if (alert.decision.toUpperCase() === 'WARN' || alert.decision.toUpperCase() === 'REVISE') {
          warnedData[lastIdx]++;
        }

        this.weeklyChartData = {
          ...this.weeklyChartData,
          datasets: [
            { ...this.weeklyChartData.datasets[0], data: blockedData },
            { ...this.weeklyChartData.datasets[1], data: warnedData },
            this.weeklyChartData.datasets[2] // Safe array remains unchanged
          ]
        };
      }

      // Update Top At-Risk Children dynamically!
      if (this.atRiskChildren) {
        const childIndex = this.atRiskChildren.findIndex(c => c.whatsapp === alert.sender);
        let updatedList = [...this.atRiskChildren];

        if (childIndex !== -1) {
          // Update existing child profile
          let child = { ...updatedList[childIndex] };
          if (alert.decision.toUpperCase() === 'BLOCK' || alert.decision.toUpperCase() === 'ESCALATE') {
            child.blocked_today++;
            child.risk_score = Math.min(1.0, child.risk_score + 0.08); // Simulate risk bump
            
            // Adjust label
            if (child.risk_score >= 0.8) child.risk_level = 'critical';
            else if (child.risk_score >= 0.5) child.risk_level = 'high';
            else child.risk_level = 'medium';
          }
          child.last_incident = 'Just now';
          updatedList[childIndex] = child;
        } else {
          // If new offender and they got blocked, add them to the board if there's room
          if (alert.decision.toUpperCase() === 'BLOCK' || alert.decision.toUpperCase() === 'ESCALATE') {
            updatedList.push({
              id: alert.sender, // Temporary ID
              name: alert.sender.split('@')[0],
              whatsapp: alert.sender,
              risk_score: 0.45,
              risk_level: 'medium',
              blocked_today: 1,
              last_incident: 'Just now'
            });
            // Keep it to Top 5
            if (updatedList.length > 5) {
              updatedList = updatedList.slice(0, 5);
            }
          }
        }
        
        // Always sort the leaderboard dynamically by highest blocks
        updatedList.sort((a, b) => b.blocked_today - a.blocked_today);
        this.atRiskChildren = updatedList;
      }
      
      this.cdr.detectChanges();
    });

    // Fetch initial historical Alerts
    this.apiService.getAlerts().subscribe({
      next: (alerts) => {
        this.recentAlerts = alerts.slice(0, 5).map(a => ({
          id: a.id,
          preview: a.raw_text.substring(0, 40) + '...',
          severity: a.decision === 'ESCALATE' || a.decision === 'BLOCK' ? 'critical' : 'medium',
          category: a.primary_class || 'Unknown',
          time: new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          decision: a.decision
        }));
        this.cdr.detectChanges();
      },
      error: (err) => console.error('[AEGIS] ❌ Failed to load ALERTS:', err)
    });

    // Fetch REAL Live Stats from PostgreSQL
    this.apiService.getDashboardStats().subscribe({
      next: (data) => {
        console.log('[AEGIS] ✅ Dashboard Stats Loaded:', data);
        
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
            label: 'AGENT 3 - LLM',
            value: data.stats.llm_interventions,
            icon: 'pi-bolt',
            trend: 'LLM',
            trendUp: true,
            color: 'accent'
          }
        ];

        this.atRiskChildren = data.at_risk_users.map(user => ({
          id: user.id,
          name: user.whatsapp.split('@')[0],
          whatsapp: user.whatsapp,
          risk_score: user.risk_score,
          risk_level: user.risk_level.toLowerCase(),
          blocked_today: user.blocked_total,
          last_incident: 'Recently'
        }));

        // Map Category Breakdown to Chart Data
        const cats = data.category_breakdown;
        this.harassmentChartData = {
          labels: ['Verbal', 'Threat', 'Sexual', 'Discrimination'],
          datasets: [{
            data: [
              cats['verbal_harassment'] || 0,
              cats['threat'] || 0,
              cats['sexual_harassment'] || 0,
              cats['discrimination'] || 0
            ],
            backgroundColor: ['#FF7A30', '#FF4D4D', '#A78BFA', '#4F7FFF'],
            borderWidth: 0,
            hoverOffset: 6
          }]
        };

        // Map Weekly Activity to Chart Data
        if (data.weekly_activity) {
           this.weeklyChartData = {
              labels: data.weekly_activity.map(w => w.day),
              datasets: [
                {
                  label: 'Blocked',
                  data: data.weekly_activity.map(w => w.blocked),
                  backgroundColor: 'rgba(239, 68, 68, 0.75)',
                  borderColor: '#EF4444',
                  borderWidth: 1,
                  borderRadius: 4,
                },
                {
                  label: 'Warned',
                  data: data.weekly_activity.map(w => w.warned),
                  backgroundColor: 'rgba(234, 179, 8, 0.65)',
                  borderColor: '#EAB308',
                  borderWidth: 1,
                  borderRadius: 4,
                },
                {
                  label: 'Safe',
                  data: data.weekly_activity.map(w => w.safe),
                  backgroundColor: 'rgba(16, 217, 160, 0.65)',
                  borderColor: '#10D9A0',
                  borderWidth: 1,
                  borderRadius: 4,
                }
              ]
           };
        }

        // Map Hourly Activity
        if (data.hourly_activity) {
          this.hourlyChartData = {
            labels: data.hourly_activity.labels,
            datasets: [
              {
                label: 'Threats',
                data: data.hourly_activity.threats,
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
                data: data.hourly_activity.safe,
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
        }

        // Map Language Distribution
        if (data.language_distribution) {
          this.languageChartData = {
            labels: data.language_distribution.labels,
            datasets: [
              {
                data: data.language_distribution.data,
                backgroundColor: ['#06B6D4', '#EAB308', '#22C55E'],
                borderWidth: 0,
                hoverOffset: 4
              }
            ]
          };
        }
        
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('[AEGIS] ❌ Failed to load stats:', err);
        this.stats = []; // Unblock UI on error
        this.cdr.detectChanges();
      }
    });
  }

  ngOnDestroy() {
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
