import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ConversationViewerComponent } from '@shared/index';
import { MOCK_CONTACTS, MOCK_MESSAGES } from './conversations.data';
import { Contact, ConversationMessage } from '@core/models';

@Component({
  selector: 'app-conversations',
  standalone: true,
  imports: [CommonModule, ConversationViewerComponent],
  templateUrl: './conversations.html',
  styleUrl: './conversations.css'
})
export class ConversationsComponent {
  contacts = signal<Contact[]>(MOCK_CONTACTS);
  messages = signal<Record<string, ConversationMessage[]>>(MOCK_MESSAGES);

  constructor(private router: Router) {}

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
