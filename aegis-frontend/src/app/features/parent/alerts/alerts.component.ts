import { Component, signal, inject, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AlertsTableComponent } from '@shared/components/alerts-table/alerts-table';
import { MockAlert } from '@core/models';
import { ApiService } from '@core/services/api.service';
import { AlertService, WebSocketAlertPayload } from '@core/services/alert.service';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { SkeletonModule } from 'primeng/skeleton';
import { Subscription } from 'rxjs';

/**
 * Maps a raw decision string to a UI severity level.
 */
function mapSeverity(decision: string): 'low' | 'medium' | 'high' | 'critical' {
  const d = (decision || '').toUpperCase();
  if (d === 'ESCALATE') return 'critical';
  if (d === 'BLOCK' || d === 'REVISE') return 'high';
  if (d === 'WARN') return 'medium';
  return 'low';
}

@Component({
  selector: 'app-parent-alerts',
  standalone: true,
  imports: [CommonModule, AlertsTableComponent, ToastModule, SkeletonModule],
  templateUrl: './alerts.html',
  styleUrl: './alerts.css'
})
export class AlertsComponent implements OnInit, OnDestroy {
  alerts = signal<MockAlert[]>([]);
  isLoading = true;
  totalAlerts = 0;

  private apiService = inject(ApiService);
  private alertService = inject(AlertService);
  private messageService = inject(MessageService);
  private cdr = inject(ChangeDetectorRef);
  private alertSub?: Subscription;

  ngOnInit() {
    // Load historical alerts from parent-scoped endpoint
    this.apiService.getParentAlerts().subscribe({
      next: (data: any[]) => {
        const history = data.map(a => ({
          id: a.id,
          sent_at: a.created_at,
          category: (a.primary_class || 'unknown').replace(/_/g, ' '),
          severity: (a.severity as 'low' | 'medium' | 'high' | 'critical') || mapSeverity(a.decision),
          is_resolved: false,
          preview: a.raw_text,
          decision: (a.decision || '').toUpperCase(),
          toxicity_score: a.toxicity_score ?? 0,
          confidence_score: a.confidence_score ?? 0,
          llm_triggered: a.llm_triggered ?? false,
          llm_explanation: a.llm_explanation ?? null,
          language: a.language || 'unknown'
        }));
        this.alerts.set(history);
        this.totalAlerts = history.length;
        this.isLoading = false;
        this.messageService.add({
          severity: 'success',
          summary: 'Alerts Synced',
          detail: 'Your child\'s security alerts are loaded.',
          life: 3000
        });

        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('[AEGIS] Failed to load parent alerts:', err);
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });

    // Listen for real-time WebSocket alerts
    this.alertSub = this.alertService.alerts$.subscribe((alert: WebSocketAlertPayload) => {
      if (alert.type === 'alert') {
        const newAlert: MockAlert = {
          id: alert.id,
          sent_at: alert.timestamp,
          category: (alert.primary_class || 'unknown').replace(/_/g, ' '),
          severity: mapSeverity(alert.decision),
          is_resolved: false,
          preview: alert.text,
          decision: (alert.decision || '').toUpperCase(),
          toxicity_score: alert.m1_score || 0,
          confidence_score: alert.m2_confidence || 0,
          llm_triggered: alert.llm_triggered || false,
          llm_explanation: alert.llm_explanation || null,
          language: alert.language || 'unknown'
        };
        this.alerts.update(list => [newAlert, ...list]);
        this.totalAlerts++;

        // Show real-time notification toast
        const decisionUpper = (alert.decision || '').toUpperCase();
        this.messageService.add({
          severity: decisionUpper === 'ESCALATE' ? 'error' : decisionUpper === 'BLOCK' ? 'warn' : 'info',
          summary: `New Alert — ${(alert.primary_class || 'unknown').replace(/_/g, ' ')}`,
          detail: alert.text.substring(0, 120),
          life: 6000,
          key: `alert-${alert.id}`,
          icon: decisionUpper === 'ESCALATE' ? 'pi pi-exclamation-circle' : 'pi pi-shield'
        });
      }
    });
  }

  ngOnDestroy() {
    if (this.alertSub) this.alertSub.unsubscribe();
  }

  onResolve(alert: MockAlert) {
    this.alerts.update(list =>
      list.map(a => a.id === alert.id ? { ...a, is_resolved: true } : a)
    );
  }
}
