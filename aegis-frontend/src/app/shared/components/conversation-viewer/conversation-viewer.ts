import { Component, input, output, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { PageHeaderComponent, getRiskHex, getDecisionClass } from '@shared/index';
import { Contact, ConversationMessage } from '@core/models';
import { SkeletonModule } from 'primeng/skeleton';
import { OnInit } from '@angular/core';

@Component({
  selector: 'app-conversation-viewer',
  standalone: true,
  imports: [CommonModule, PageHeaderComponent, RouterModule, SkeletonModule],
  templateUrl: './conversation-viewer.html',
  styleUrl: './conversation-viewer.css'
})
export class ConversationViewerComponent implements OnInit {
  contacts = input.required<Contact[]>();
  messages = input.required<Record<string, ConversationMessage[]>>();
  isAdmin = input<boolean>(false);
  title = input<string>('Conversations');
  subtitle = input<string>('Investigative context layer: read full history before taking action');

  openRiskProfileEvent = output<{tab: 'children' | 'contacts', contact: Contact}>();
  goToReportsEvent = output<void>();

  view = signal<'table' | 'chat'>('table');
  selectedContact = signal<Contact | null>(null);
  
  isLoading = signal(true);
  skeletonItems = [1, 2, 3, 4, 5];
  mobileView = signal<'list' | 'chat'>('list');
  searchTerm = signal('');
  riskFilter = signal<'all' | 'high' | 'blocked'>('all');
  selectedAlertMessage = signal<ConversationMessage | null>(null);

  getRiskHex = getRiskHex;
  getDecisionClass = getDecisionClass;

  get filteredContacts(): Contact[] {
    const term = this.searchTerm().toLowerCase();
    const filtered = this.contacts().filter(c =>
      c.number.toLowerCase().includes(term) ||
      c.child_name.toLowerCase().includes(term) ||
      c.parent_name.toLowerCase().includes(term) ||
      (c.name?.toLowerCase().includes(term))
    );

    const mode = this.riskFilter();
    if (mode === 'high') {
      return filtered.filter(c => c.risk_level === 'high' || c.risk_level === 'critical');
    }
    if (mode === 'blocked') {
      return filtered.filter(c => c.blocked_count > 0);
    }
    return filtered;
  }

  getMessagesForContact(contactId: string): ConversationMessage[] {
    return this.messages()[contactId] ?? [];
  }

  ngOnInit() {
    setTimeout(() => {
      this.isLoading.set(false);
    }, 800);
  }

  openChat(contact: Contact) {
    this.selectedContact.set(contact);
    this.mobileView.set('list');
    this.view.set('chat');
    this.closeAlertDrawer();
  }

  openFirstFlaggedFromList(contact: Contact) {
    this.openChat(contact);
    const firstFlagged = this.getMessagesForContact(contact.id).find(msg => this.isFlaggedMessage(msg));
    if (firstFlagged) {
      this.openAlertDrawer(firstFlagged);
    }
  }

  backToTable() {
    this.view.set('table');
    this.selectedContact.set(null);
  }

  selectContact(contact: Contact) {
    this.selectedContact.set(contact);
    this.mobileView.set('chat');
  }

  backToList() {
    this.mobileView.set('list');
  }

  isWarnMessage(msg: ConversationMessage): boolean {
    return msg.decision === 'WARN';
  }

  isFlaggedMessage(msg: ConversationMessage): boolean {
    return msg.decision === 'WARN' || msg.decision === 'BLOCK' || msg.decision === 'ESCALATE';
  }

  getPlatformTagClass(platform: Contact['plateforme']): string {
    if (platform === 'WhatsApp') return 'platform-wa';
    if (platform === 'Telegram') return 'platform-tg';
    return 'platform-sim';
  }

  getSenderRiskColor(score: number): string {
    if (score >= 0.85) return 'var(--critical)';
    if (score >= 0.70) return 'var(--high)';
    if (score >= 0.50) return 'var(--medium)';
    return 'var(--low)';
  }

  openAlertDrawer(msg: ConversationMessage) {
    this.selectedAlertMessage.set(msg);
  }

  closeAlertDrawer() {
    this.selectedAlertMessage.set(null);
  }

  openRiskProfile(tab: 'children' | 'contacts', contact: Contact) {
    this.openRiskProfileEvent.emit({ tab, contact });
  }

  goToReports() {
    this.goToReportsEvent.emit();
  }

  exportConversation() {
    const contact = this.selectedContact();
    if (!contact) return;

    const rows = this.getMessagesForContact(contact.id).map(msg => {
      const decision = msg.decision ?? '-';
      const toxicity = msg.toxicity_score !== null ? msg.toxicity_score.toFixed(2) : '-';
      return `[${msg.sent_at}] ${msg.direction.toUpperCase()} (${msg.language}) ${decision} Tox:${toxicity} :: ${msg.content_preview}`;
    });

    const header = [
      `Conversation Evidence Export`,
      `Contact: ${contact.sender_name} (${contact.number})`,
      `Child: ${contact.child_name}`,
      `Platform: ${contact.plateforme}`,
      `Risk: ${contact.risk_level} (${contact.sender_risk_score.toFixed(2)})`,
      ''
    ].join('\n');

    const content = `${header}${rows.join('\n')}`;
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `conversation-${contact.id}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
}
