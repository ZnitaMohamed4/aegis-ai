import { Component, signal, OnInit, OnDestroy, inject, ViewChildren, QueryList } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ChartModule, UIChart } from 'primeng/chart';
import { SkeletonModule } from 'primeng/skeleton';
import { DialogModule } from 'primeng/dialog';
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
import { MessageService } from 'primeng/api';
import { WhatsappJidPipe } from '@shared/pipes/whatsapp-jid.pipe';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, ChartModule, SkeletonModule, DialogModule, WhatsappJidPipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class DashboardComponent implements OnInit, OnDestroy {

  stats: any[] | null = null;
  latencies: any = null;
  pushNotificationsCount: number = 0;
  recentAlerts: any[] | null = null;
  atRiskChildren: any[] | null = null;
  // adding an evol api property
  isEvolutionOnline: boolean = false; // Will be set by API
  
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
  private readonly MAX_FEED = 5;
  feedDialogVisible: boolean = false;
  selectedFeedEvent: FeedEvent | null = null;

  private alertService = inject(AlertService);
  private alertSub?: Subscription;
  private apiService = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  private messageService = inject(MessageService);

  ngOnInit() {
    // Subscribe to WebSockets for Live Alerts
    this.alertSub = this.alertService.alerts$.subscribe((alert: WebSocketAlertPayload) => {
      let feedText = '';
      let feedIcon = 'pi-info-circle';
      let cleanText = (alert.text || "(Media/Sticker)").substring(0, 50) + "...";
      let shortSender = alert.sender.split('@')[0];
      
      if (alert.llm_triggered) {
        const shortReason = (alert.llm_explanation || '').substring(0, 70) + ((alert.llm_explanation || '').length > 70 ? '…' : '');
        feedText = `Agent 3 (LLM) forced [${alert.decision.toUpperCase()}] for ${shortSender} — ${shortReason}`;
        feedIcon = 'pi-bolt';
      } else {
        switch(alert.decision.toUpperCase()) {
          case 'ALLOW':
            feedText = `Message from ${shortSender} passed safely`;
            feedIcon = 'pi-verified';
            break;
          case 'WARN':
            feedText = `Issued automated warning for [${(alert.primary_class || '').toUpperCase()}] on ${shortSender}`;
            feedIcon = 'pi-exclamation-triangle';
            break;
          case 'BLOCK':
          case 'ESCALATE':
            feedText = `ACTIVE SHIELD Blocked [${(alert.primary_class || '').toUpperCase()}] with ${Math.round(alert.m1_score * 100)}% severity`;
            feedIcon = 'pi-ban';
            break;
          case 'REVISE':
            feedText = `Grey-zone message from ${shortSender} under review`;
            feedIcon = 'pi-eye';
            break;
          case 'HUMAN_REVIEW':
            feedText = `Message from ${shortSender} sent to review`;
            feedIcon = 'pi-user';
            break;
          default:
            feedText = `Analyzed incoming message from ${shortSender}`;
        }
      }

      const newEvent: FeedEvent = {
        id: alert.id,
        time: new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        type: alert.decision.toLowerCase() as any,
        icon: feedIcon,
        text: feedText,
        fullText: (() => {
          if (alert.decision.toUpperCase() === 'ALLOW' || !alert.text) {
            return '\u2705 This message was analyzed and cleared. Content is not stored to protect user privacy.';
          }
          return alert.llm_explanation ? `Text: ${alert.text}\n\nLLM Explanation:\n${alert.llm_explanation}` : alert.text;
        })()
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

        // 0. Increment 'Total Messages Today'
        this.stats[0].value = Number(this.stats[0].value) + 1;
        // 1. Always increment 'Total Alerts Today' and 'Push Notifications'
        this.stats[1].value = Number(this.stats[1].value) + 1;
        this.pushNotificationsCount++;
        
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
        const datasets = [...this.harassmentChartData.datasets];
        const dataArr = [...datasets[0].data];
        
        switch (alert.primary_class.toLowerCase()) {
          case 'verbal_harassment': dataArr[0]++; break;
          case 'threat': dataArr[1]++; break;
          case 'sexual_harassment': dataArr[2]++; break;
          case 'discrimination': dataArr[3]++; break;
        }
        
        datasets[0] = { ...datasets[0], data: dataArr };
        this.harassmentChartData = { ...this.harassmentChartData, datasets };
      }

      // Update Weekly Bar Chart dynamically! (Adding to today's bar)
      if (this.weeklyChartData) {
        const datasets = [...this.weeklyChartData.datasets];
        
        const blockedData = [...datasets[0].data];
        const warnedData = [...datasets[1].data];
        const safeData = [...datasets[2].data];
        const lastIdx = blockedData.length - 1; // Today is the last entry
        
        if (alert.decision.toUpperCase() === 'BLOCK' || alert.decision.toUpperCase() === 'ESCALATE') {
          blockedData[lastIdx]++;
        } else if (alert.decision.toUpperCase() === 'WARN' || alert.decision.toUpperCase() === 'REVISE') {
          warnedData[lastIdx]++;
        } else if (alert.decision.toUpperCase() === 'ALLOW') {
          safeData[lastIdx]++;
        }

        datasets[0] = { ...datasets[0], data: blockedData };
        datasets[1] = { ...datasets[1], data: warnedData };
        datasets[2] = { ...datasets[2], data: safeData };

        this.weeklyChartData = { ...this.weeklyChartData, datasets };
      }

      // Update Hourly Chart dynamically!
      if (this.hourlyChartData) {
        const datasets = [...this.hourlyChartData.datasets];
        const threatsData = [...datasets[0].data];
        const safeData = [...datasets[1].data];
        
        // Find current hour bucket (0-23 => index 0-11)
        const hour = new Date().getHours();
        const bucketIdx = Math.floor(hour / 2);
        
        if (['BLOCK', 'ESCALATE', 'WARN', 'REVISE'].includes(alert.decision.toUpperCase())) {
          threatsData[bucketIdx]++;
        } else if (alert.decision.toUpperCase() === 'ALLOW') {
          safeData[bucketIdx]++;
        }

        datasets[0] = { ...datasets[0], data: threatsData };
        datasets[1] = { ...datasets[1], data: safeData };

        this.hourlyChartData = { ...this.hourlyChartData, datasets };
      }

      // Update Language Chart dynamically!
      if (this.languageChartData && alert.language) {
        const datasets = [...this.languageChartData.datasets];
        const dataArr = [...datasets[0].data];
        const labels = [...this.languageChartData.labels];
        
        const langIdx = labels.findIndex(l => l.toLowerCase() === alert.language?.toLowerCase());
        
        if (langIdx !== -1) {
          dataArr[langIdx]++;
        } else {
          labels.push(alert.language.toUpperCase());
          dataArr.push(1);
          // ensure multiple background colors are available or add a random one
          const colors = datasets[0].backgroundColor;
          if (colors.length < labels.length) {
              colors.push('#' + Math.floor(Math.random()*16777215).toString(16).padStart(6, '0'));
          }
        }

        datasets[0] = { ...datasets[0], data: dataArr };
        this.languageChartData = { ...this.languageChartData, labels, datasets };
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

    // Fetch initial Activity Feed — seeds from /activity/ (includes ALLOW events)
    this.apiService.getActivityFeed().subscribe({
      next: (events) => {
        // Seed the Activity Feed from DB (persists across page refreshes, includes ALLOW)
        const seedEvents: FeedEvent[] = events.slice(0, this.MAX_FEED).map((a: any) => {
          const decision = (a.decision || '').toUpperCase();
          const shortSender = (a.sender_jid || '').split('@')[0];
          const cleanText = (a.raw_text || '(no text)').substring(0, 50) + '...';
          let feedText = '';
          let feedIcon = 'pi-info-circle';

          if (a.llm_triggered && a.llm_explanation) {
            const shortReason = a.llm_explanation.substring(0, 70) + (a.llm_explanation.length > 70 ? '…' : '');
            feedText = `Agent 3 (LLM) forced [${decision}] for ${shortSender} — ${shortReason}`;
            feedIcon = 'pi-bolt';
          } else {
            switch (decision) {
              case 'ALLOW':
                feedText = `Message from ${shortSender} passed safely`;
                feedIcon = 'pi-verified';
                break;
              case 'WARN':
                feedText = `Issued automated warning for [${(a.primary_class || '').toUpperCase()}] on ${shortSender}`;
                feedIcon = 'pi-exclamation-triangle';
                break;
              case 'BLOCK':
              case 'ESCALATE':
                feedText = `ACTIVE SHIELD Blocked [${(a.primary_class || '').toUpperCase()}] with ${Math.round((a.toxicity_score || 0) * 100)}% severity`;
                feedIcon = 'pi-ban';
                break;
              case 'REVISE':
                feedText = `Grey-zone message from ${shortSender} under review`;
                feedIcon = 'pi-eye';
                break;
              case 'HUMAN_REVIEW':
                feedText = `Message from ${shortSender} sent to review`;
                feedIcon = 'pi-user';
                break;
              default:
                feedText = `Analyzed incoming message from ${shortSender}`;
            }
          }

          return {
            id: a.id,
            time: new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            type: decision.toLowerCase() as any,
            icon: feedIcon,
            text: feedText,
            fullText: (() => {
              if (decision === 'ALLOW' || !a.raw_text) {
                return '\u2705 This message was analyzed and cleared. Content is not stored to protect user privacy.';
              }
              return a.llm_explanation ? `Text: ${a.raw_text}\n\nLLM Explanation:\n${a.llm_explanation}` : a.raw_text;
            })()
          };
        });

        // Only set if feed is currently empty (don't overwrite live events)
        this.feedEvents.update(existing => existing.length === 0 ? seedEvents : existing);
        this.cdr.detectChanges();
      },
      error: (err) => console.error('[AEGIS] Failed to load activity feed:', err)
    });

    // Fetch initial historical Alerts — seeds the recent alerts panel
    this.apiService.getAlerts().subscribe({
      next: (alerts) => {
        // Seed the "Recent Alerts" panel (top 5)
        this.recentAlerts = alerts.slice(0, 5).map((a: any) => ({
          id: a.id,
          preview: a.raw_text.substring(0, 40) + '...',
          severity: a.severity || (a.decision === 'ESCALATE' ? 'critical' : a.decision === 'BLOCK' ? 'high' : a.decision === 'WARN' ? 'medium' : 'low'),
          category: a.primary_class || 'Unknown',
          time: new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          decision: (a.decision || '').toUpperCase()
        }));
        this.cdr.detectChanges();
      },
      error: (err) => console.error('[AEGIS] Failed to load ALERTS:', err)
    });

    // Fetch REAL Live Stats from PostgreSQL
    this.apiService.getDashboardStats().subscribe({
      next: (data) => {
        console.log('[AEGIS] ✅ Dashboard Stats Loaded:', data);
        
        this.latencies = data.stats.latencies;
        this.pushNotificationsCount = data.stats.total_alerts_today;
        this.isEvolutionOnline = data.stats.evolution_api_online;
        
        this.stats = [
          {
            label: 'Messages Today',
            value: data.stats.total_messages_today || 0,
            icon: 'pi-envelope',
            trend: 'Live from DB',
            trendUp: true,
            color: 'info'
          },
          {
            label: 'Total Alerts Today',
            value: data.stats.total_alerts_today || 0,
            icon: 'pi-bell',
            trend: 'Live from DB',
            trendUp: true,
            color: 'critical'
          },
          {
            label: 'Messages Blocked',
            value: data.stats.total_blocked_today || 0,
            icon: 'pi-ban',
            trend: 'Live from DB',
            trendUp: true,
            color: 'high'
          },
          {
            label: 'AGENT 3 - LLM',
            value: data.stats.llm_interventions || 0,
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
                backgroundColor: ['#06B6D4', '#EAB308', '#22C55E', '#A855F7', '#EC4899', '#64748B'],
                borderWidth: 0,
                hoverOffset: 4
              }
            ]
          };
        }
        
        this.messageService.add({
          severity: 'success',
          summary: 'Global Data Synced',
          detail: 'Dashboard metrics are up to date.',
          life: 3000
        });

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

  showFeedDetails(event: FeedEvent) {
    this.selectedFeedEvent = event;
    this.feedDialogVisible = true;
  }

  flagForReview(event: FeedEvent) {
    if (!event.id || event.flagged) return;
    
    event.flagged = true; // optimistically mark it locally
    
    this.apiService.flagForReview(event.id.toString()).subscribe({
      next: () => {
      },
      error: (err) => {
        console.error('Failed to flag message:', err);
        event.flagged = false;
      }
    });
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
