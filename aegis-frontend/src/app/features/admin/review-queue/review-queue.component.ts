import { Component, signal, computed, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../../core/services/api.service';
import { AlertService, WebSocketAlertPayload } from '../../../core/services/alert.service';
import { MessageService, ConfirmationService } from 'primeng/api';
import { QueueReason, RiskLevel } from './review-queue.data';
import { WhatsappJidPipe } from '../../../shared/pipes/whatsapp-jid.pipe';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-review-queue',
  standalone: true,
  imports: [CommonModule, FormsModule, WhatsappJidPipe],
  templateUrl: './review-queue.html',
  styleUrl: './review-queue.css'
})
export class ReviewQueueComponent implements OnInit, OnDestroy {
  items = signal<any[]>([]);
  loading = signal(true);
  submittingIds = signal<Set<string>>(new Set());
  
  resolvedCount = signal(0);
  blockedCount = signal(0);
  warnedCount = signal(0);
  allowedCount = signal(0);
  totalCount = 0;

  // For the UI to store the local override state before submitting
  localOverrides = signal<Record<string, { label: string, note: string }>>({});

  private apiService = inject(ApiService);
  private alertService = inject(AlertService);
  private messageService = inject(MessageService);
  private confirmationService = inject(ConfirmationService);
  private alertSub?: Subscription;

  pendingItems = computed(() => this.items());

  ngOnInit() {
    this.loadQueue();

    // Live WebSocket updates: Auto-add new HUMAN_REVIEW items
    this.alertSub = this.alertService.alerts$.subscribe((alert: WebSocketAlertPayload) => {
      const decision = (alert.decision || '').toUpperCase();
      if (decision === 'HUMAN_REVIEW' || decision === 'REVISE') {
        // Refetch the queue to get the full item data
        this.apiService.getReviewQueue().subscribe({
          next: (data) => {
            this.items.set(data);
            this.totalCount = data.length + this.resolvedCount();
            this.syncOverrides(data);
            
            // Notify admin of new item
            this.messageService.add({
              severity: 'info',
              summary: 'New Item in Queue',
              detail: `A ${decision} message needs your attention.`,
              life: 5000,
              icon: 'pi pi-inbox'
            });
          }
        });
      }
    });
  }

  ngOnDestroy() {
    if (this.alertSub) this.alertSub.unsubscribe();
  }

  private loadQueue() {
    this.loading.set(true);
    this.apiService.getReviewQueue().subscribe({
      next: (data) => {
        this.items.set(data);
        this.totalCount = data.length;
        this.syncOverrides(data);
        this.loading.set(false);
      },
      error: (err) => {
        console.error('Failed to load Review Queue:', err);
        this.loading.set(false);
        this.messageService.add({
          severity: 'error',
          summary: 'Connection Error',
          detail: 'Failed to load the review queue. Is the backend running?',
          life: 6000
        });
      }
    });
  }

  // Removed loadStats() as the stats are session-only and start at 0

  private syncOverrides(data: any[]) {
    const overrides: any = {};
    for (const item of data) {
      overrides[item.id] = {
        label: item.primary_class || 'safe',
        note: ''
      };
    }
    this.localOverrides.set(overrides);
  }

  getLabelColor(label: string): string {
    const map: Record<string, string> = {
      'threat': '#FF4D4D',
      'verbal_harassment': '#FF7A30',
      'sexual_harassment': '#A78BFA',
      'discrimination': '#4F7FFF',
      'safe': '#10D9A0'
    };
    return map[label.toLowerCase()] ?? '#7A9CC9';
  }

  formatTime(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' }) +
      ' · ' + date.toLocaleDateString('en', { month: 'short', day: 'numeric' });
  }

  isSubmitting(itemId: string): boolean {
    return this.submittingIds().has(itemId);
  }

  confirmAndSubmit(item: any, finalDecision: string) {
    const decisionLabel = finalDecision === 'BLOCK' ? 'Block' : finalDecision === 'WARN' ? 'Warn' : 'Allow (Safe)';
    const decisionColor = finalDecision === 'BLOCK' ? 'danger' : finalDecision === 'WARN' ? 'warning' : 'success';
    const override = this.localOverrides()[item.id] || { label: item.primary_class, note: '' };
    
    this.confirmationService.confirm({
      message: `Are you sure you want to <strong>${decisionLabel}</strong> this message?<br/><br/>
        <em>"${(item.raw_text || '').substring(0, 80)}${item.raw_text?.length > 80 ? '...' : ''}"</em><br/><br/>
        Label: <strong>${(override.label || 'unchanged').replace(/_/g, ' ')}</strong>`,
      header: 'Confirm Override',
      icon: finalDecision === 'BLOCK' ? 'pi pi-ban' : finalDecision === 'WARN' ? 'pi pi-exclamation-triangle' : 'pi pi-check',
      acceptLabel: decisionLabel,
      rejectLabel: 'Cancel',
      accept: () => this.submitOverride(item, finalDecision),
    });
  }

  submitOverride(item: any, finalDecision: string) {
    const override = this.localOverrides()[item.id] || { label: item.primary_class, note: '' };
    
    // Mark as submitting
    this.submittingIds.update(ids => {
      const next = new Set(ids);
      next.add(item.id);
      return next;
    });

    this.apiService.humanOverride(item.id, finalDecision, override.label, override.note).subscribe({
      next: (res) => {
        if (finalDecision === 'BLOCK') this.blockedCount.update(c => c + 1);
        else if (finalDecision === 'WARN') this.warnedCount.update(c => c + 1);
        else if (finalDecision === 'ALLOW') this.allowedCount.update(c => c + 1);
        
        this.resolvedCount.update(c => c + 1);
        this.items.update(list => list.filter(i => i.id !== item.id));

        // Remove from submittingIds
        this.submittingIds.update(ids => {
          const next = new Set(ids);
          next.delete(item.id);
          return next;
        });

        const decisionLabel = finalDecision === 'BLOCK' ? 'Blocked' : finalDecision === 'WARN' ? 'Warned' : 'Allowed';
        this.messageService.add({
          severity: finalDecision === 'BLOCK' ? 'error' : finalDecision === 'WARN' ? 'warn' : 'success',
          summary: `Override Applied: ${decisionLabel}`,
          detail: res.original_ai_decision 
            ? `AI originally decided ${res.original_ai_decision} → You overrode to ${finalDecision}. Saved for retraining.` 
            : `Decision changed to ${finalDecision}. Label: ${override.label.replace(/_/g, ' ')}.`,
          life: 4000
        });
      },
      error: (err) => {
        // Remove from submittingIds
        this.submittingIds.update(ids => {
          const next = new Set(ids);
          next.delete(item.id);
          return next;
        });

        const errorMsg = err.error?.reason || err.message || 'Unknown error';
        
        // Handle 409 Conflict (already reviewed)
        if (err.status === 409) {
          this.messageService.add({
            severity: 'warn',
            summary: 'Already Reviewed',
            detail: `Another admin already reviewed this message. Refreshing queue...`,
            life: 5000
          });
          // Refresh the queue
          this.loadQueue();
        } else {
          this.messageService.add({
            severity: 'error',
            summary: 'Override Failed',
            detail: `Could not apply override: ${errorMsg}`,
            life: 5000
          });
        }
      }
    });
  }

  updateLocalLabel(itemId: string, newLabel: string) {
    this.localOverrides.update(current => {
      return { 
        ...current, 
        [itemId]: { ...current[itemId], label: newLabel } 
      };
    });
  }

  updateLocalNote(itemId: string, newNote: string) {
    this.localOverrides.update(current => {
      return { 
        ...current, 
        [itemId]: { ...current[itemId], note: newNote } 
      };
    });
  }

  getDecisionIcon(decision: string): string {
    const map: Record<string, string> = {
      'BLOCK': 'pi-ban',
      'ESCALATE': 'pi-arrow-up-right',
      'WARN': 'pi-exclamation-triangle',
      'REVISE': 'pi-eye',
      'HUMAN_REVIEW': 'pi-user',
      'ALLOW': 'pi-check'
    };
    return map[decision] ?? 'pi-question-circle';
  }
}
