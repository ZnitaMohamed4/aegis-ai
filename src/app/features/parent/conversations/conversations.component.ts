import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ConversationViewerComponent } from '@shared/index';
import { Contact, ConversationMessage } from '@core/models';
import { EMMA_CONTACTS, EMMA_MESSAGES } from './parent-conversations.data';

@Component({
  selector: 'app-conversations',
  standalone: true,
  imports: [CommonModule, ConversationViewerComponent],
  templateUrl: './conversations.html',
  styleUrl: './conversations.css'
})
export class ConversationsComponent {
  // Parent only sees their child's contacts
  contacts = signal<Contact[]>(EMMA_CONTACTS);
  messages = signal<Record<string, ConversationMessage[]>>(EMMA_MESSAGES);

  constructor(private router: Router) {}

  onOpenRiskProfile(event: {tab: 'children' | 'contacts', contact: Contact}) {
    // Parents don't navigate to admin risk profiles, they go to their child's risk profile
    this.router.navigate(['/parent/risk-profile']);
  }

  onGoToReports() {
    this.router.navigate(['/parent/reports']);
  }
}
