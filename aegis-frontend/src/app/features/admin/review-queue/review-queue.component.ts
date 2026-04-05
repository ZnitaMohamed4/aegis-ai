import { Component, signal, computed, HostListener, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ReviewItem, MOCK_REVIEW_ITEMS, SIMILAR_DECISIONS, SimilarDecision, QueueReason, RiskLevel } from './review-queue.data';

@Component({
  selector: 'app-review-queue',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './review-queue.html',
  styleUrl: './review-queue.css'
})
export class ReviewQueueComponent implements OnInit {

  items = signal<ReviewItem[]>(MOCK_REVIEW_ITEMS);
  resolvedCount = signal(0);
  blockedCount = signal(0);
  allowedCount = signal(0);
  totalCount = MOCK_REVIEW_ITEMS.length;

  // Flashcard mode
  flashcardMode = signal(true);
  currentIndex = signal(0);
  animating = signal<'out-left' | 'out-right' | 'out-up' | null>(null);

  // Track model agreement
  modelAgreements = signal(0);

  pendingItems = computed(() => this.items());
  currentItem = computed(() => this.items()[this.currentIndex()]);

  avgConfidence = computed(() => {
    const list = this.items();
    if (list.length === 0) return 0;
    return list.reduce((sum, i) => sum + i.confidence_score, 0) / list.length;
  });

  progressPercent = computed(() => {
    if (this.totalCount === 0) return 100;
    return (this.resolvedCount() / this.totalCount) * 100;
  });

  agreementPercent = computed(() => {
    const reviewed = this.resolvedCount();
    if (reviewed === 0) return 0;
    return Math.round((this.modelAgreements() / reviewed) * 100);
  });

  ngOnInit() {
    // Focus the component for keyboard shortcuts
  }

  // Keyboard shortcuts: B = Block, A = Allow, S = Skip
  @HostListener('document:keydown', ['$event'])
  handleKeyboardShortcut(event: KeyboardEvent) {
    if (!this.flashcardMode() || this.animating() || !this.currentItem()) return;
    
    const key = event.key.toLowerCase();
    if (key === 'b') {
      event.preventDefault();
      this.confirmBlock(this.currentItem()!);
    } else if (key === 'a') {
      event.preventDefault();
      this.allowMessage(this.currentItem()!);
    } else if (key === 's') {
      event.preventDefault();
      this.skipItem();
    }
  }

  getSimilarDecisions(label: string): SimilarDecision[] {
    return SIMILAR_DECISIONS[label] ?? [];
  }

  getBlockPercent(label: string): number {
    const similar = this.getSimilarDecisions(label);
    if (similar.length === 0) return 0;
    const blocked = similar.filter(s => s.decision === 'BLOCK').length;
    return Math.round((blocked / similar.length) * 100);
  }

  getQueueReasonLabel(reason: QueueReason): string {
    return reason === 'SCORE_AMBIGU' ? 'SCORE AMBIGU' : 'LANGUE NON IDENTIFIABLE';
  }

  getQueueReasonColor(reason: QueueReason): string {
    return reason === 'SCORE_AMBIGU' ? '#FFB020' : '#A78BFA';
  }

  getRiskLevelColor(level: RiskLevel): string {
    const map: Record<RiskLevel, string> = {
      'low': '#10D9A0',
      'medium': '#FFB020',
      'high': '#FF7A30',
      'critical': '#FF4D4D'
    };
    return map[level];
  }

  getRiskLevelLabel(level: RiskLevel): string {
    const map: Record<RiskLevel, string> = {
      'low': 'Low Risk',
      'medium': 'Medium Risk',
      'high': 'High Risk',
      'critical': 'Critical'
    };
    return map[level];
  }

  getWaitingTime(submittedAt: string): { text: string; isUrgent: boolean } {
    const submitted = new Date(submittedAt);
    const now = new Date();
    const diffMs = now.getTime() - submitted.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const hours = Math.floor(diffMins / 60);
    const mins = diffMins % 60;

    let text: string;
    if (hours > 0) {
      text = `waiting ${hours}h ${mins}min`;
    } else {
      text = `waiting ${mins}min`;
    }

    return { text, isUrgent: diffMins > 30 };
  }

  getScoreColor(score: number): string {
    if (score >= 0.7) return '#FF4D4D';
    if (score >= 0.5) return '#FFB020';
    return '#10D9A0';
  }

  confirmBlock(item: ReviewItem) {
    // Model suggested block if confidence > 0.65 and toxicity > 0.65
    const modelSuggestedBlock = item.toxicity_score > 0.65;
    if (modelSuggestedBlock) {
      this.modelAgreements.update(c => c + 1);
    }

    // Update item with audit trail
    const updatedItem = { 
      ...item, 
      reviewed_by: 'Admin',
      reviewed_at: new Date().toISOString()
    };

    this.blockedCount.update(c => c + 1);
    
    if (this.flashcardMode()) {
      this.animateAndRemove(updatedItem, 'out-left');
    } else {
      this.removeItem(updatedItem);
    }
  }

  allowMessage(item: ReviewItem) {
    // Model suggested allow if confidence < 0.7 and toxicity < 0.6
    const modelSuggestedAllow = item.toxicity_score < 0.6;
    if (modelSuggestedAllow) {
      this.modelAgreements.update(c => c + 1);
    }

    // Update item with audit trail
    const updatedItem = { 
      ...item, 
      reviewed_by: 'Admin',
      reviewed_at: new Date().toISOString()
    };

    this.allowedCount.update(c => c + 1);
    
    if (this.flashcardMode()) {
      this.animateAndRemove(updatedItem, 'out-right');
    } else {
      this.removeItem(updatedItem);
    }
  }

  skipItem() {
    this.animating.set('out-up');
    setTimeout(() => {
      this.animating.set(null);
      const list = this.items();
      if (list.length <= 1) return;
      // Move current item to end
      const current = list[this.currentIndex()];
      this.items.update(l => {
        const copy = [...l];
        copy.splice(this.currentIndex(), 1);
        copy.push(current);
        return copy;
      });
      if (this.currentIndex() >= this.items().length) {
        this.currentIndex.set(0);
      }
    }, 250);
  }

  private animateAndRemove(item: ReviewItem, direction: 'out-left' | 'out-right') {
    this.animating.set(direction);
    setTimeout(() => {
      this.animating.set(null);
      this.removeItem(item);
    }, 250);
  }

  private removeItem(item: ReviewItem) {
    this.items.update(list => list.filter(i => i.id !== item.id));
    this.resolvedCount.update(c => c + 1);
    if (this.currentIndex() >= this.items().length && this.items().length > 0) {
      this.currentIndex.set(0);
    }
  }

  toggleMode() {
    this.flashcardMode.update(v => !v);
    this.currentIndex.set(0);
  }

  getConfidenceColor(score: number): string {
    if (score >= 0.72) return '#FF7A30';
    if (score >= 0.68) return '#FFB020';
    return '#7A9CC9';
  }

  getLabelColor(label: string): string {
    const map: Record<string, string> = {
      'Threat': '#FF4D4D',
      'Verbal Harassment': '#FF7A30',
      'Sexual Harassment': '#A78BFA',
      'Discrimination': '#4F7FFF',
      'Safe': '#10D9A0'
    };
    return map[label] ?? '#7A9CC9';
  }

  formatTime(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' }) +
      ' · ' + date.toLocaleDateString('en', { month: 'short', day: 'numeric' });
  }

  formatPrevMessageTime(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' });
  }

  getConfidenceWidth(score: number): string {
    return `${score * 100}%`;
  }
}
