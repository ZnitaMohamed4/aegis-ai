import { Component, signal, OnInit, OnDestroy, inject, ViewChildren, QueryList, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ChartModule, UIChart } from 'primeng/chart';
import { SkeletonModule } from 'primeng/skeleton';
import { DialogModule } from 'primeng/dialog';
import { ToastModule } from 'primeng/toast';
import { getRiskHex, getDecisionClass } from '@shared/utils/severity.utils';
import {
  HARASSMENT_CHART_OPTIONS,
  WEEKLY_CHART_OPTIONS,
  HOURLY_CHART_OPTIONS,
  LANGUAGE_CHART_OPTIONS,
  FeedEvent
} from '@features/admin/dashboard/dashboard.data';
import { ApiService, ParentChildInfo } from '@core/services/api.service';
import { AlertService, WebSocketAlertPayload } from '@core/services/alert.service';
import { AuthService } from '@core/services/auth.service';
import { Subscription } from 'rxjs';
import { MessageService } from 'primeng/api';
import { WhatsappJidPipe } from '@shared/pipes/whatsapp-jid.pipe';

@Component({
  selector: 'app-parent-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, ChartModule, SkeletonModule, DialogModule, ToastModule, WhatsappJidPipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class DashboardComponent implements OnInit, OnDestroy {

  // Child info from backend
  childInfo: ParentChildInfo | null = null;
  childName: string = 'Your Child';
  monitoringMode: string = 'child';

  // Stats
  stats: any[] | null = null;
  recentAlerts: any[] | null = null;

  // Charts
  harassmentChartData: any = null;
  harassmentChartOptions = HARASSMENT_CHART_OPTIONS;
  weeklyChartData: any = null;
  weeklyChartOptions = WEEKLY_CHART_OPTIONS;
  hourlyChartData: any = null;
  hourlyChartOptions = HOURLY_CHART_OPTIONS;
  languageChartData: any = null;
  languageChartOptions = LANGUAGE_CHART_OPTIONS;

  // Risky contacts
  riskyContacts: any[] | null = null;

  // Emotional Pattern Heatmap
  heatmapData: any = null;

  // Severity utils
  getRiskHex = getRiskHex;
  getDecisionClass = getDecisionClass;

  // Live activity feed
  feedEvents = signal<FeedEvent[]>([]);
  private readonly MAX_FEED = 5;
  feedDialogVisible: boolean = false;
  selectedFeedEvent: FeedEvent | null = null;

  // Services
  private apiService = inject(ApiService);
  private alertService = inject(AlertService);
  private authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  private messageService = inject(MessageService);
  private alertSub?: Subscription;

  ngOnInit() {
    // Show loading toast

    this.authService.currentUser$.subscribe(user => {
      if (user && user.monitoring_mode) {
        this.monitoringMode = user.monitoring_mode;
      }
    });

    // ── WebSocket: Live alerts (filter client-side to this parent's instance) ──
    this.alertSub = this.alertService.alerts$.subscribe((alert: WebSocketAlertPayload) => {
      // Build feed event text
      let feedText = '';
      let feedIcon = 'pi-info-circle';
      const cleanText = (alert.text || "(Media/Sticker)").substring(0, 50) + "...";
      let shortSender = alert.sender.split('@')[0];
      if (alert.sender.includes('@g.us') || shortSender.length > 15) {
        shortSender = 'Group Chat';
      } else if (/^\d+$/.test(shortSender)) {
        shortSender = '+' + shortSender;
      }

      if (alert.llm_triggered) {
        const shortReason = (alert.llm_explanation || '').substring(0, 70) + ((alert.llm_explanation || '').length > 70 ? '…' : '');
        feedText = `AI reviewed message from ${shortSender} — ${shortReason}`;
        feedIcon = 'pi-bolt';
      } else {
        switch(alert.decision.toUpperCase()) {
          case 'ALLOW':
            feedText = `Message from ${shortSender} passed safely`;
            feedIcon = 'pi-verified';
            break;
          case 'WARN':
            feedText = `Warning issued for ${(alert.primary_class || '').replace(/_/g, ' ')} from ${shortSender}`;
            feedIcon = 'pi-exclamation-triangle';
            break;
          case 'BLOCK':
          case 'ESCALATE':
            feedText = `🛡️ Blocked ${(alert.primary_class || '').replace(/_/g, ' ')} from ${shortSender}`;
            feedIcon = 'pi-ban';
            break;
          case 'EDUCATE':
            feedText = `🎓 Aegis guided your child toward better digital habits`;
            feedIcon = 'pi-book';
            break;
          case 'SELF_WARN':
            feedText = `💭 Self-reflection nudge for ${(alert.primary_class || '').replace(/_/g, ' ')}`;
            feedIcon = 'pi-heart';
            break;
          default:
            feedText = `Message analyzed from ${shortSender}`;
        }
      }

      const newEvent: FeedEvent = {
        id: alert.id,
        time: new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        type: alert.decision.toLowerCase() as any,
        icon: feedIcon,
        text: feedText,
        // Privacy: only show raw message content for flagged (harmful) events.
        // ALLOW events show privacy notice; EDUCATE events show what the bot said.
        fullText: (() => {
          const dec = alert.decision.toUpperCase();
          if (dec === 'ALLOW') return '\u2705 This message was analyzed and cleared. Content is not stored to protect your child\'s privacy.';
          if (dec === 'EDUCATE') return alert.llm_explanation
            ? `🎓 Aegis intercepted a message and sent your child this educational note:\n\n"${alert.llm_explanation}"`
            : '🎓 Aegis intercepted a message and sent your child a friendly educational reminder.';
          return alert.llm_explanation
            ? `Message: ${alert.text}\n\nAI Analysis:\n${alert.llm_explanation}`
            : alert.text;
        })()
      };

      this.feedEvents.update(list => {
        const next = [newEvent, ...list];
        return next.slice(0, this.MAX_FEED);
      });

      // Live update recent alerts
      if (this.recentAlerts && alert.type === 'alert') {
        const dec = (alert.decision || '').toUpperCase();
        this.recentAlerts = [{
          id: alert.id,
          preview: alert.text.length > 50 ? alert.text.substring(0, 50) + "..." : alert.text,
          severity: alert.severity,
          category: alert.primary_class,
          time: 'Just now',
          decision: dec === 'SELF_WARN' ? 'REFLECTION' : dec
        }, ...this.recentAlerts].slice(0, 5);
      }

      // Live update stat cards
      if (this.stats) {
        this.stats[1].value = Number(this.stats[1].value) + 1;
        if (['BLOCK', 'ESCALATE', 'SELF_WARN'].includes(alert.decision.toUpperCase())) {
          this.stats[2].value = Number(this.stats[2].value) + 1;
        }
      }

      // Live update donut chart
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

      // Live update weekly chart
      if (this.weeklyChartData) {
        const datasets = [...this.weeklyChartData.datasets];
        const blockedData = [...datasets[0].data];
        const warnedData = [...datasets[1].data];
        const safeData = [...datasets[2].data];
        const lastIdx = blockedData.length - 1;
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

      // Live update hourly chart
      if (this.hourlyChartData) {
        const datasets = [...this.hourlyChartData.datasets];
        const threatsData = [...datasets[0].data];
        const safeData = [...datasets[1].data];
        const bucketIdx = Math.floor(new Date().getHours() / 2);
        if (['BLOCK', 'ESCALATE', 'WARN', 'REVISE'].includes(alert.decision.toUpperCase())) {
          threatsData[bucketIdx]++;
        } else if (alert.decision.toUpperCase() === 'ALLOW') {
          safeData[bucketIdx]++;
        }
        datasets[0] = { ...datasets[0], data: threatsData };
        datasets[1] = { ...datasets[1], data: safeData };
        this.hourlyChartData = { ...this.hourlyChartData, datasets };
      }



      // Show toast for harmful alerts
      if (alert.type === 'alert' && alert.decision.toUpperCase() !== 'ALLOW') {
      }

      this.cdr.detectChanges();
    });

    // ── Fetch parent-scoped activity feed ──
    this.apiService.getParentActivityFeed().subscribe({
      next: (events) => {
        const seedEvents: FeedEvent[] = events.slice(0, this.MAX_FEED).map((a: any) => {
          const decision = (a.decision || '').toUpperCase();
          let shortSender = (a.sender_jid || '').split('@')[0];
          if ((a.sender_jid || '').includes('@g.us') || shortSender.length > 15) {
            shortSender = 'Group Chat';
          } else if (/^\d+$/.test(shortSender)) {
            shortSender = '+' + shortSender;
          }
          const cleanText = (a.raw_text || '(no text)').substring(0, 50) + '...';
          let feedText = '';
          let feedIcon = 'pi-info-circle';

          if (a.llm_triggered && a.llm_explanation) {
            const shortReason = a.llm_explanation.substring(0, 70) + (a.llm_explanation.length > 70 ? '…' : '');
            feedText = `AI reviewed message from ${shortSender} — ${shortReason}`;
            feedIcon = 'pi-bolt';
          } else {
            switch (decision) {
              case 'ALLOW':
                feedText = `Message from ${shortSender} passed safely`;
                feedIcon = 'pi-verified';
                break;
              case 'WARN':
                feedText = `Warning issued for ${(a.primary_class || '').replace(/_/g, ' ')} from ${shortSender}`;
                feedIcon = 'pi-exclamation-triangle';
                break;
              case 'BLOCK':
              case 'ESCALATE':
                feedText = `🛡️ Blocked ${(a.primary_class || '').replace(/_/g, ' ')} from ${shortSender}`;
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
              case 'EDUCATE':
                feedText = `🎓 Aegis guided your child toward better digital habits`;
                feedIcon = 'pi-book';
                break;
              case 'SELF_WARN':
                feedText = `💭 Self-reflection nudge for ${(a.primary_class || '').replace(/_/g, ' ')}`;
                feedIcon = 'pi-heart';
                break;
              default:
                feedText = `Message analyzed from ${shortSender}`;
            }
          }

          return {
            id: a.id,
            time: new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            type: decision.toLowerCase() as any,
            icon: feedIcon,
            text: feedText,
            // Privacy: safe messages never show raw content; educate shows the bot DM
            fullText: (() => {
              if (decision === 'ALLOW' || !a.raw_text) {
                return '\u2705 This message was analyzed and cleared. Content is not stored to protect your child\'s privacy.';
              }
              if (decision === 'EDUCATE') {
                return a.educational_dm_text
                  ? `🎓 Aegis intercepted a message and sent your child this note:\n\n"${a.educational_dm_text}"`
                  : '🎓 Aegis intercepted a message and sent your child a friendly educational reminder.';
              }
              return a.llm_explanation
                ? `Message: ${a.raw_text}\n\nAI Analysis:\n${a.llm_explanation}`
                : a.raw_text;
            })()
          };
        });

        this.feedEvents.update(existing => existing.length === 0 ? seedEvents : existing);
        this.cdr.detectChanges();
      },
      error: (err) => console.error('[AEGIS] Failed to load parent activity feed:', err)
    });

    // ── Fetch parent-scoped alerts ──
    this.apiService.getParentAlerts().subscribe({
      next: (alerts) => {
        this.recentAlerts = alerts.slice(0, 5).map((a: any) => {
          const dec = (a.decision || '').toUpperCase();
          return {
            id: a.id,
            preview: a.raw_text.substring(0, 40) + '...',
            severity: a.severity || (dec === 'ESCALATE' ? 'critical' : dec === 'BLOCK' ? 'high' : dec === 'WARN' ? 'medium' : 'low'),
            category: a.primary_class || 'Unknown',
            time: new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            decision: dec === 'SELF_WARN' ? 'REFLECTION' : dec
          };
        });
        this.cdr.detectChanges();
      },
      error: (err) => console.error('[AEGIS] Failed to load parent alerts:', err)
    });

    // ── Fetch REAL parent-scoped stats ──
    this.apiService.getParentDashboardStats().subscribe({
      next: (data) => {
        console.log('[AEGIS] ✅ Parent Dashboard Stats Loaded:', data);

        // Set child info
        this.childInfo = data.child;
        this.childName = data.child?.name || 'Your Child';

        const isAdult = this.monitoringMode === 'adult';
        this.stats = [
          {
            label: 'Messages Analyzed',
            value: data.stats.total_messages_all_time,
            icon: 'pi-comments',
            trend: `${data.stats.total_messages_today} new today`,
            trendUp: data.stats.total_messages_today >= 0,
            color: 'accent'
          },
          {
            label: isAdult ? 'Self-Reflection Alerts' : 'Active Alerts',
            value: data.stats.total_alerts_all_time,
            icon: isAdult ? 'pi-heart' : 'pi-bell',
            trend: `${data.stats.total_alerts_today} new today`,
            trendUp: data.stats.total_alerts_today === 0,
            color: data.stats.total_alerts_today > 0 ? 'critical' : 'low'
          },
          {
            label: isAdult ? 'Messages Flagged' : 'Threats Blocked',
            value: data.stats.total_blocked_all_time,
            icon: isAdult ? 'pi-flag' : 'pi-shield',
            trend: `${data.stats.total_blocked_today} new today`,
            trendUp: true,
            color: data.stats.total_blocked_today > 0 ? 'high' : 'low'
          },
          {
            label: isAdult ? 'Wellness Score' : 'Risk Level',
            value: this.getRiskLabel(data.child?.risk_level || 'LOW'),
            icon: isAdult ? 'pi-heart-fill' : 'pi-chart-line',
            trend: isAdult ? 'Self-monitoring Active' : (data.child?.is_monitored ? 'Monitoring Active' : (data.child ? 'Not Monitoring' : 'No child linked')),
            trendUp: (data.child?.risk_level || 'low').toLowerCase() === 'low',
            color: this.getRiskColor(data.child?.risk_level || 'low')
          }
        ];

        // Risky contacts
        this.riskyContacts = (data.at_risk_contacts || []).map((c: any) => {
          let displayName = c.whatsapp.split('@')[0];
          if (c.whatsapp.includes('@g.us') || displayName.length > 15) {
            displayName = 'Group Chat';
          } else if (/^\d+$/.test(displayName)) {
            displayName = '+' + displayName;
          }
          return {
            id: c.id,
            name: displayName,
            whatsapp: c.whatsapp,
            risk_score: c.risk_score,
            risk_level: c.risk_level.toLowerCase(),
            blocked_total: c.blocked_total,
            last_incident: 'Recently'
          };
        });

        // Category breakdown → Donut chart
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

        // Weekly Activity → Bar chart
        if (data.weekly_activity) {
          this.weeklyChartData = {
            labels: data.weekly_activity.map(w => w.day),
            datasets: [
              {
                label: isAdult ? 'Flagged' : 'Blocked',
                data: data.weekly_activity.map(w => w.blocked),
                backgroundColor: 'rgba(239, 68, 68, 0.75)',
                borderColor: '#EF4444',
                borderWidth: 1,
                borderRadius: 4,
              },
              {
                label: isAdult ? 'Reflected' : 'Warned',
                data: data.weekly_activity.map(w => w.warned),
                backgroundColor: 'rgba(234, 179, 8, 0.65)',
                borderColor: '#EAB308',
                borderWidth: 1,
                borderRadius: 4,
              },
              {
                label: isAdult ? 'Cleared' : 'Safe',
                data: data.weekly_activity.map(w => w.safe),
                backgroundColor: 'rgba(16, 217, 160, 0.65)',
                borderColor: '#10D9A0',
                borderWidth: 1,
                borderRadius: 4,
              }
            ]
          };
        }

        // Hourly Activity → Line chart
        if (data.hourly_activity) {
          this.hourlyChartData = {
            labels: data.hourly_activity.labels,
            datasets: [
              {
                label: isAdult ? 'Flagged' : 'Threats',
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
                label: isAdult ? 'Cleared' : 'Safe',
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

        // Language distribution → Doughnut
        if (data.language_distribution) {
          this.languageChartData = {
            labels: data.language_distribution.labels,
            datasets: [{
              data: data.language_distribution.data,
              backgroundColor: ['#06B6D4', '#EAB308', '#22C55E', '#A855F7', '#EC4899', '#64748B'],
              borderWidth: 0,
              hoverOffset: 4
            }]
          };
        }

        // Success toast
        this.messageService.add({
          severity: 'success',
          summary: this.monitoringMode === 'adult' ? 'Wellness Data Synced' : 'Child Data Synced',
          detail: 'Dashboard metrics are up to date.',
          life: 3000
        });

        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('[AEGIS] ❌ Failed to load parent stats:', err);
        this.stats = [];
        this.cdr.detectChanges();
      }
    });

    // ── Fetch Emotional Heatmap ──
    this.apiService.getEmotionalHeatmap(30).subscribe({
      next: (data) => {
        this.heatmapData = data;
        this.cdr.detectChanges();
      },
      error: (err) => console.error('[AEGIS] Failed to load heatmap:', err)
    });
  }

  ngOnDestroy() {
    if (this.alertSub) this.alertSub.unsubscribe();
  }

  showFeedDetails(event: FeedEvent) {
    this.selectedFeedEvent = event;
    this.feedDialogVisible = true;
  }

  getFeedColor(type: string): string {
    const map: Record<string, string> = {
      block: 'var(--critical)',
      escalate: 'var(--high)',
      warn: 'var(--medium)',
      allow: 'var(--low)',
      review: 'var(--accent)',
      risk: 'var(--high)',
      educate: 'var(--accent)',
      human_review: 'var(--accent)',
      revise: 'var(--medium)',
      self_warn: '#A78BFA',        // Soft purple — gentle adult self-reflection
    };
    return map[type] ?? 'var(--text-muted)';
  }

  getRiskBarWidth(score: number): string {
    return `${score * 100}%`;
  }

  getRiskColor(level: string): string {
    const l = (level || 'low').toLowerCase();
    if (l === 'critical') return 'critical';
    if (l === 'high') return 'high';
    if (l === 'medium') return 'medium';
    return 'low';
  }

  getRiskLabel(level: string): string {
    const l = (level || 'LOW').toUpperCase();
    if (this.monitoringMode === 'adult') {
      if (l === 'CRITICAL') return 'STRESSED';
      if (l === 'HIGH') return 'ELEVATED';
      if (l === 'MEDIUM') return 'AWARE';
      return 'BALANCED';
    }
    return l;
  }

  getHeatmapColor(count: number): string {
    if (count === 0) return 'var(--surface-b)';
    if (this.monitoringMode === 'adult') {
      if (count <= 1) return 'rgba(167, 139, 250, 0.35)';   // light purple
      if (count <= 3) return 'rgba(139, 92, 246, 0.55)';    // medium purple
      if (count <= 5) return 'rgba(124, 58, 237, 0.7)';     // dark purple
      return 'rgba(109, 40, 217, 0.9)';                     // very dark purple
    }
    if (count <= 1) return 'rgba(234, 179, 8, 0.35)';    // light amber
    if (count <= 3) return 'rgba(249, 115, 22, 0.55)';   // orange
    if (count <= 5) return 'rgba(239, 68, 68, 0.7)';     // red
    return 'rgba(220, 38, 38, 0.9)';                      // dark red
  }
}
