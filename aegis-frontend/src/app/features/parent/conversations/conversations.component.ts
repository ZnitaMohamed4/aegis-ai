import { Component, signal, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ConversationViewerComponent } from '@shared/index';
import { Contact, ConversationMessage } from '@core/models';
import { ApiService } from '@core/services/api.service';

@Component({
  selector: 'app-conversations',
  standalone: true,
  imports: [CommonModule, ConversationViewerComponent],
  templateUrl: './conversations.html',
  styleUrl: './conversations.css'
})
export class ConversationsComponent implements OnInit {
  contacts = signal<Contact[]>([]);
  messages = signal<Record<string, ConversationMessage[]>>({});

  private apiService = inject(ApiService);
  private router = inject(Router);

  ngOnInit() {
    this.apiService.getParentConversations().subscribe({
      next: (data: any) => {
        const contactsList: Contact[] = [];
        const messagesMap: Record<string, ConversationMessage[]> = {};
        
        for (const c of data.contacts || []) {
          contactsList.push({
            id: c.id,
            name: c.name.split('@')[0], // Clean up JID a bit
            number: c.name.split('@')[0],
            child_name: 'Your Child',
            child_id: '1',
            parent_name: 'You',
            sender_name: c.name.split('@')[0],
            sender_risk_score: c.risk_score !== undefined ? c.risk_score : 0.5,
            risk_level: c.risk_level || 'low',
            plateforme: 'WhatsApp',
            is_first_contact: false,
            last_message: c.messages?.[c.messages.length - 1]?.content || '',
            last_message_at: c.messages?.[c.messages.length - 1]?.timestamp || new Date().toISOString(),
            total_messages: c.messages?.length || 0,
            blocked_count: c.messages?.filter((m: any) => m.is_blocked).length || 0,
            unread: 0
          } as Contact);

          messagesMap[c.id] = c.messages.map((m: any) => ({
            id: m.id,
            content_preview: m.content,
            direction: m.direction as 'incoming' | 'outgoing',
            is_blocked: m.is_blocked,
            language: 'UNKNOWN',
            sent_at: m.timestamp,
            decision: m.decision || (m.is_blocked ? 'BLOCK' : 'ALLOW'),
            toxicity_score: m.toxicity_score !== undefined ? m.toxicity_score : 0,
            category: m.category || (m.is_blocked ? 'harassment' : null),
            llm_triggered: !!m.ai_explanation
          } as ConversationMessage));
        }
        
        this.contacts.set(contactsList);
        this.messages.set(messagesMap);
      },
      error: (err) => console.error('[AEGIS] Failed to load conversations', err)
    });
  }

  onOpenRiskProfile(event: {tab: 'children' | 'contacts', contact: Contact}) {
    // Parents navigate to their child's risk profile
    this.router.navigate(['/parent/risk-profile']);
  }

  onGoToReports() {
    this.router.navigate(['/parent/reports']);
  }
}
