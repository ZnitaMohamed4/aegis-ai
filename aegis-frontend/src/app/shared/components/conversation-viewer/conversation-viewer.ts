import { Component, input, output, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { PageHeaderComponent, getRiskHex, getDecisionClass } from '@shared/index';
import { Contact, ConversationMessage } from '@core/models';
import { SkeletonModule } from 'primeng/skeleton';
import { OnInit, effect } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

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

  constructor(private route: ActivatedRoute, private router: Router) {
    // Sync URL to State on route changes
    this.route.queryParams.subscribe(params => {
      this.syncStateWithUrl(params);
    });

    // Sync URL to State once contacts load from backend
    effect(() => {
      if (this.contacts().length > 0) {
        this.syncStateWithUrl(this.route.snapshot.queryParams);
      }
    });
  }

  syncStateWithUrl(params: any) {
    const filter = params['filter'];
    if (filter === 'flagged' || filter === 'blocked') {
      this.messageFilter.set(filter);
    } else {
      this.messageFilter.set('all');
    }

    if (params['child']) {
      this.selectedChildGroupId.set(params['child']);
      this.view.set('table');
    }
    if (params['chat']) {
      const chatParam = params['chat'];
      const contact = this.contacts().find(c => c.id === chatParam || c.raw_jid === chatParam);
      if (contact) {
        this.selectedContact.set(contact);
        this.view.set('chat');
        
        // If it was matched by raw_jid, convert the URL param to the specific conversation id
        if (contact.id !== chatParam) {
          setTimeout(() => {
            this.router.navigate([], {
              relativeTo: this.route,
              queryParams: { chat: contact.id },
              queryParamsHandling: 'merge',
              replaceUrl: true
            });
          });
        }
      }
    }
    if (!params['child'] && !params['chat']) {
      if (this.isAdmin()) this.view.set('children');
      else this.view.set('table');
    }
  }

  view = signal<'children' | 'table' | 'chat'>('table');
  selectedContact = signal<Contact | null>(null);
  selectedChildGroupId = signal<string | null>(null);
  messageFilter = signal<'all' | 'flagged' | 'blocked'>('all');
  
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
    
    // If admin and a child is selected, filter by that child id first
    let baseContacts = this.contacts();
    const selChild = this.selectedChildGroupId();
    if (this.isAdmin() && selChild) {
      baseContacts = baseContacts.filter(c => c.child_id === selChild);
    }
    
    const filtered = baseContacts.filter(c =>
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
  
  get childGroups() {
    const groups = new Map<string, { child_id: string, child_name: string, risk_level: string, contacts: Contact[], total_messages: number, blocked_count: number }>();
    for (const c of this.contacts()) {
      if (!groups.has(c.child_id)) {
        groups.set(c.child_id, { child_id: c.child_id, child_name: c.child_name, risk_level: 'low', contacts: [], total_messages: 0, blocked_count: 0 });
      }
      const g = groups.get(c.child_id)!;
      g.contacts.push(c);
      g.total_messages += c.total_messages;
      g.blocked_count += c.blocked_count;
      if (c.risk_level === 'high' || c.risk_level === 'critical') g.risk_level = c.risk_level;
      else if (g.risk_level === 'low' && c.risk_level === 'medium') g.risk_level = 'medium';
    }
    return Array.from(groups.values());
  }

  getMessagesForContact(contactId: string): ConversationMessage[] {
    const msgs = this.messages()[contactId] ?? [];
    if (this.messageFilter() === 'blocked') {
      return msgs.filter(msg => msg.decision === 'BLOCK' || msg.decision === 'ESCALATE');
    }
    if (this.messageFilter() === 'flagged') {
      return msgs.filter(msg => this.isFlaggedMessage(msg));
    }
    return msgs;
  }

  ngOnInit() {
    setTimeout(() => {
      this.isLoading.set(false);
    }, 800);
  }

  openTableForChild(childId: string) {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { child: childId },
      queryParamsHandling: 'merge'
    });
  }

  backToChildren() {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { child: null, chat: null, filter: null },
      queryParamsHandling: 'merge'
    });
  }

  openChat(contact: Contact) {
    this.closeAlertDrawer();
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { chat: contact.id, filter: null },
      queryParamsHandling: 'merge'
    });
  }

  openFirstFlaggedFromList(contact: Contact) {
    this.closeAlertDrawer();
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { chat: contact.id, filter: 'blocked' },
      queryParamsHandling: 'merge'
    });
  }

  backToTable() {
    const childId = this.selectedChildGroupId();
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { chat: null, child: childId || null, filter: null },
      queryParamsHandling: 'merge'
    });
    this.selectedContact.set(null);
  }

  toggleMessageFilter() {
    const current = this.messageFilter();
    let next = 'all';
    // Cycle logic: all -> blocked -> flagged -> all
    if (current === 'all') next = 'blocked';
    else if (current === 'blocked') next = 'flagged';
    
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { filter: next === 'all' ? null : next },
      queryParamsHandling: 'merge'
    });
  }

  clearFilter() {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { filter: null },
      queryParamsHandling: 'merge'
    });
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
