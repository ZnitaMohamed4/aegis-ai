import { Component, computed, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SkeletonModule } from 'primeng/skeleton';

interface BlockedMessage {
  id: string;
  senderName: string;
  senderAvatar: string;
  timestamp: string;
  snippet: string;
  fullMessage: string;
  aiReason: string;
  aiExplanation: string;
  confidenceScore: number;
}

@Component({
  selector: 'app-blocked-messages',
  standalone: true,
  imports: [CommonModule, SkeletonModule],
  templateUrl: './blocked-messages.html',
  styleUrls: ['./blocked-messages.css']
})
export class BlockedMessagesComponent implements OnInit {
  
  MOCK_BLOCKED_MESSAGES: BlockedMessage[] = [
    {
      id: 'msg-1',
      senderName: 'Unknown Number',
      senderAvatar: 'https://ui-avatars.com/api/?name=U+N&background=ef4444&color=fff',
      timestamp: 'Today, 2:15 PM',
      snippet: 'You are so stupid and everyone hates...',
      fullMessage: 'You are so stupid and everyone hates you. Just drop out already.',
      aiReason: 'verbal_harassment',
      aiExplanation: 'Our AI detected aggressive and insulting language directed at your child. It was blocked before they could see it.',
      confidenceScore: 0.94
    },
    {
      id: 'msg-2',
      senderName: 'Alex (School)',
      senderAvatar: 'https://ui-avatars.com/api/?name=A&background=3b82f6&color=fff',
      timestamp: 'Yesterday, 8:30 PM',
      snippet: 'Send me those pictures now or else...',
      fullMessage: 'Send me those pictures now or else I will tell everyone your secret.',
      aiReason: 'extortion_threat',
      aiExplanation: 'Our AI detected a threat or attempt at extortion. It was blocked to protect your child from emotional manipulation.',
      confidenceScore: 0.89
    },
    {
      id: 'msg-3',
      senderName: '+44 7911 123456',
      senderAvatar: 'https://ui-avatars.com/api/?name=44&background=64748b&color=fff',
      timestamp: 'Monday, 11:45 AM',
      snippet: 'Click here to claim your free Robux...',
      fullMessage: 'Click here to claim your free Robux: http://suspicious-link.net/promo',
      aiReason: 'phishing_spam',
      aiExplanation: 'Our AI detected a malicious link designed to steal personal information or account credentials. It was blocked for safety.',
      confidenceScore: 0.98
    }
  ];

  isLoading = signal(true);
  skeletonItems = [1, 2, 3, 4, 5];

  selectedMessageId = signal<string | null>(this.MOCK_BLOCKED_MESSAGES[0].id);

  selectedMessage = computed(() => {
    return this.MOCK_BLOCKED_MESSAGES.find(m => m.id === this.selectedMessageId()) || null;
  });

  showTechnicalDetails = signal<boolean>(false);

  selectMessage(id: string) {
    this.selectedMessageId.set(id);
    this.showTechnicalDetails.set(false); // Reset toggle on new selection
  }

  toggleTechnicalDetails() {
    this.showTechnicalDetails.update(v => !v);
  }

  ngOnInit() {
    setTimeout(() => {
      this.isLoading.set(false);
    }, 800);
  }
}
