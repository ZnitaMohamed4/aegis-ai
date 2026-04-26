import { Component, input, output, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { PageHeaderComponent, getRiskHex, getDecisionClass } from '@shared/index';
import { Contact, ConversationMessage } from '@core/models';
import { SkeletonModule } from 'primeng/skeleton';
import { OnInit, effect } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { DrawerModule } from 'primeng/drawer';

@Component({
  selector: 'app-conversation-viewer',
  standalone: true,
  imports: [CommonModule, PageHeaderComponent, RouterModule, SkeletonModule, DrawerModule],
  templateUrl: './conversation-viewer.html',
  styleUrl: './conversation-viewer.css'
})
export class ConversationViewerComponent implements OnInit {
  contacts = input.required<Contact[]>();
  messages = input.required<Record<string, ConversationMessage[]>>();
  isAdmin = input<boolean>(false);
  title = input<string>('Message Intelligence');
  subtitle = input<string>('Contact safety overview — flagged threat events only');

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
    if (params['child']) {
      this.selectedChildGroupId.set(params['child']);
      this.view.set('table');
    }
    if (params['contact']) {
      const contactParam = params['contact'];
      const contact = this.contacts().find(c => c.id === contactParam || c.raw_jid === contactParam);
      if (contact) {
        this.selectedContact.set(contact);
        this.threatDrawerVisible.set(true);

        // Normalize URL param to the specific conversation id
        if (contact.id !== contactParam) {
          setTimeout(() => {
            this.router.navigate([], {
              relativeTo: this.route,
              queryParams: { contact: contact.id },
              queryParamsHandling: 'merge',
              replaceUrl: true
            });
          });
        }
      }
    }
    if (!params['child'] && !params['contact']) {
      if (this.isAdmin()) this.view.set('children');
      else this.view.set('table');
    }
  }

  view = signal<'children' | 'table'>('table');
  selectedContact = signal<Contact | null>(null);
  selectedChildGroupId = signal<string | null>(null);
  threatDrawerVisible = signal(false);

  isLoading = signal(true);
  skeletonItems = [1, 2, 3, 4, 5];
  searchTerm = signal('');
  riskFilter = signal<'all' | 'high' | 'blocked'>('all');

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

  /** Returns ONLY flagged messages for a contact — safe messages are never exposed. */
  getFlaggedMessages(contactId: string): ConversationMessage[] {
    const msgs = this.messages()[contactId] ?? [];
    return msgs.filter(msg => this.isFlaggedMessage(msg));
  }

  /** Returns count of safe (ALLOW) messages for a contact. */
  getSafeMessageCount(contactId: string): number {
    const msgs = this.messages()[contactId] ?? [];
    return msgs.filter(msg => msg.decision === 'ALLOW').length;
  }

  /** Generates a threat summary string for the table view. */
  getThreatSummary(contact: Contact): string {
    const flagged = this.getFlaggedMessages(contact.id);
    if (flagged.length === 0) return 'No threats detected';
    const blocks = flagged.filter(m => m.decision === 'BLOCK' || m.decision === 'ESCALATE').length;
    const warns = flagged.filter(m => m.decision === 'WARN').length;
    const parts: string[] = [];
    if (blocks > 0) parts.push(`${blocks} blocked`);
    if (warns > 0) parts.push(`${warns} warned`);
    const lastCategory = flagged[flagged.length - 1]?.category;
    if (lastCategory && lastCategory !== 'safe') parts.push(`last: ${lastCategory}`);
    return parts.join(', ');
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
      queryParams: { child: null, contact: null },
      queryParamsHandling: 'merge'
    });
  }

  /** Opens the threat detail drawer for a contact. */
  openThreatDrawer(contact: Contact) {
    this.selectedContact.set(contact);
    this.threatDrawerVisible.set(true);
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { contact: contact.id },
      queryParamsHandling: 'merge'
    });
  }

  /** Closes the threat detail drawer. */
  closeThreatDrawer() {
    this.threatDrawerVisible.set(false);
    this.selectedContact.set(null);
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { contact: null },
      queryParamsHandling: 'merge'
    });
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

  getDecisionColor(decision: string): string {
    if (decision === 'ESCALATE') return 'var(--critical)';
    if (decision === 'BLOCK') return 'var(--high)';
    if (decision === 'WARN') return 'var(--medium)';
    return 'var(--low)';
  }

  getDecisionIcon(decision: string): string {
    if (decision === 'ESCALATE') return 'pi-exclamation-triangle';
    if (decision === 'BLOCK') return 'pi-ban';
    if (decision === 'WARN') return 'pi-exclamation-circle';
    return 'pi-check-circle';
  }

  openRiskProfile(tab: 'children' | 'contacts', contact: Contact) {
    this.openRiskProfileEvent.emit({ tab, contact });
  }

  goToReports() {
    this.goToReportsEvent.emit();
  }

  /** Exports metadata-only evidence log — NO raw message text. */
  exportEvidenceLog() {
    const contact = this.selectedContact();
    if (!contact) return;

    const flagged = this.getFlaggedMessages(contact.id);
    const rows = flagged.map(msg => {
      const toxicity = msg.toxicity_score !== null ? msg.toxicity_score.toFixed(2) : '-';
      return `[${msg.sent_at}] ${msg.direction.toUpperCase()} | Decision: ${msg.decision} | Category: ${msg.category || '-'} | Toxicity: ${toxicity} | Language: ${msg.language} | LLM: ${msg.llm_triggered ? 'YES' : 'NO'}`;
    });

    const safeCount = this.getSafeMessageCount(contact.id);

    const header = [
      `AEGIS — Threat Evidence Log`,
      `Generated: ${new Date().toISOString()}`,
      ``,
      `Contact: ${contact.sender_name} (${contact.number})`,
      `Child: ${contact.child_name}`,
      `Platform: ${contact.plateforme}`,
      `Risk Level: ${contact.risk_level} (Score: ${contact.sender_risk_score.toFixed(2)})`,
      ``,
      `Total Messages: ${contact.total_messages}`,
      `Safe Messages: ${safeCount} (content not recorded)`,
      `Flagged Events: ${flagged.length}`,
      ``,
      `--- FLAGGED EVENTS ---`,
      ``
    ].join('\n');

    const content = `${header}${rows.join('\n')}`;
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `aegis-evidence-${contact.id}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
}
