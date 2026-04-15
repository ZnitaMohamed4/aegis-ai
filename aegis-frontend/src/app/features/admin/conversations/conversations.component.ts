import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ConversationViewerComponent } from '@shared/index';
import { MOCK_CONTACTS, MOCK_MESSAGES } from './conversations.data';
import { Contact, ConversationMessage } from '@core/models';
import { ApiService } from '@core/services/api.service';

@Component({
  selector: 'app-conversations',
  standalone: true,
  imports: [CommonModule, ConversationViewerComponent],
  templateUrl: './conversations.html',
  styleUrl: './conversations.css'
})
export class ConversationsComponent {
  contacts = signal<Contact[]>([]);
  messages = signal<Record<string, ConversationMessage[]>>({});

  constructor(private router: Router, private apiService: ApiService) {}

  ngOnInit() {
    this.apiService.getAdminConversations().subscribe({
      next: (data) => {
        this.contacts.set(data.contacts);
        this.messages.set(data.messages);
      },
      error: (err) => {
        console.error('Failed to load conversations from backend. Falling back to mock data.', err);
        this.contacts.set(MOCK_CONTACTS);
        this.messages.set(MOCK_MESSAGES);
      }
    });
  }

  onOpenRiskProfile(event: {tab: 'children' | 'contacts', contact: Contact}) {
    this.router.navigate(['/admin/risk-profiles'], {
      queryParams: {
        tab: event.tab,
        child: event.tab === 'children' ? event.contact.child_id : undefined,
        contact: event.tab === 'contacts' ? event.contact.id : undefined
      }
    });
  }

  onGoToReports() {
    this.router.navigate(['/admin/reports']);
  }
}
