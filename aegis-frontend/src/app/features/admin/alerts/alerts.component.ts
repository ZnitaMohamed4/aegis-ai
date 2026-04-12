import { Component, signal, inject, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AlertsTableComponent } from '@shared/components/alerts-table/alerts-table';
import { MockAlert } from '@core/models';
import { ApiService } from '@core/services/api.service';
import { AlertService, WebSocketAlertPayload } from '@core/services/alert.service';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { Subscription } from 'rxjs';

/**
 * Maps a raw decision string to a UI severity level.
 * Used for real-time WS alerts where SecurityAlert.severity is not yet available.
 * For historical data, the backend now sends severity directly — prefer that.
 */
function mapSeverity(decision: string): 'low' | 'medium' | 'high' | 'critical' {
  const d = (decision || '').toUpperCase();
  if (d === 'ESCALATE') return 'critical';
  if (d === 'BLOCK' || d === 'REVISE') return 'high';
  if (d === 'WARN') return 'medium';
  return 'low'; // ALLOW
}

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [CommonModule, AlertsTableComponent, ToastModule],
  templateUrl: './alerts.html',
  styleUrl: './alerts.css'
})
export class AlertsComponent implements OnInit, OnDestroy {
  alerts = signal<MockAlert[]>([]);

  private apiService = inject(ApiService);
  private alertService = inject(AlertService);
  private messageService = inject(MessageService);
  private cdr = inject(ChangeDetectorRef);
  private alertSub?: Subscription;

  ngOnInit() {
    // Load historical alerts from the backend (now includes WARN + real severity)
    this.apiService.getAlerts().subscribe({
      next: (data: any[]) => {
        const history = data.map(a => ({
          id: a.id,
          sent_at: a.created_at,
          category: (a.primary_class || 'unknown').replace(/_/g, ' '),
          // Prefer the severity field the backend now sends (source of truth from SecurityAlert)
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


        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('[AEGIS] Failed to load alerts history:', err);
      }
    });

    // Listen for real-time WebSocket alerts
    this.alertSub = this.alertService.alerts$.subscribe((alert: WebSocketAlertPayload) => {
      if (alert.type === 'alert') {
        const decisionUpper = (alert.decision || '').toUpperCase();
        this.messageService.add({
          severity: decisionUpper === 'ESCALATE' ? 'error' : decisionUpper === 'BLOCK' ? 'warn' : 'info',
          summary: `New Alert — ${(alert.primary_class || 'unknown').replace(/_/g, ' ')}`,
          detail: alert.text.substring(0, 120),
          life: 6000,
          key: `alert-${alert.id}`,
          icon: decisionUpper === 'ESCALATE' ? 'pi pi-exclamation-circle' : 'pi pi-shield'
        });

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
