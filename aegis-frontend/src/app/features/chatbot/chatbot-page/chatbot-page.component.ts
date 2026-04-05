import { Component, signal, effect, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

export interface Source {
  name: string;
  score: number;
}

export interface ThinkingStep {
  label: string;
  status: 'pending' | 'running' | 'done';
}

export interface Message {
  id: string;
  role: 'bot' | 'user';
  text: string;
  sources?: Source[];
  thinkingSteps?: ThinkingStep[];
  timestamp: Date;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  updatedAt: Date;
}

@Component({
  selector: 'app-chatbot-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chatbot-page.html',
  styleUrl: './chatbot-page.css',
})
export class ChatbotPageComponent {
  // UI States
  isSidebarOpen = signal(true);
  webSearchEnabled = signal(false);
  agentModeEnabled = signal(false);
  activeLanguage = signal<'fr' | 'ar' | 'en'>(this.getSystemLanguage());
  
  // Chat Data
  conversations = signal<Conversation[]>([
    {
      id: '1',
      title: 'Loi 103-13 et protection des données',
      updatedAt: new Date(),
      messages: [
        {
          id: '101',
          role: 'bot',
          text: 'Bonjour ! Comment puis-je vous aider avec la base de connaissance AEGIS aujourd\'hui ?',
          timestamp: new Date(Date.now() - 1000000),
        }
      ]
    },
    {
      id: '2',
      title: 'Signalement cyberharcèlement DGSN',
      updatedAt: new Date(Date.now() - 86400000),
      messages: []
    }
  ]);
  
  activeConversationId = signal<string>('1');
  inputText = '';
  isTyping = signal(false);

  activeConversation = signal<Conversation | undefined>(undefined);

  constructor() {
    effect(() => {
      const conv = this.conversations().find(c => c.id === this.activeConversationId());
      this.activeConversation.set(conv);
    }, { allowSignalWrites: true });
  }

  private getSystemLanguage(): 'fr' | 'ar' | 'en' {
    const lang = navigator.language.split('-')[0];
    if (['fr', 'ar', 'en'].includes(lang)) return lang as any;
    return 'fr';
  }

  selectConversation(id: string) {
    this.activeConversationId.set(id);
  }

  newChat() {
    const newConv: Conversation = {
      id: Math.random().toString(36).substring(7),
      title: 'Nouvelle conversation',
      messages: [
        {
          id: crypto.randomUUID(),
          role: 'bot',
          text: 'Nouvelle session démarrée. Posez-moi une question.',
          timestamp: new Date(),
        }
      ],
      updatedAt: new Date()
    };
    this.conversations.update(prev => [newConv, ...prev]);
    this.activeConversationId.set(newConv.id);
  }

  sendMessage() {
    if (!this.inputText.trim() || this.isTyping()) return;

    const userText = this.inputText;
    this.inputText = '';
    
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      text: userText,
      timestamp: new Date()
    };

    this.updateMessages(userMsg);
    this.simulateResponse(userText);
  }

  private updateMessages(msg: Message) {
    this.conversations.update(prev => prev.map(c => {
      if (c.id === this.activeConversationId()) {
        const updatedMessages = [...c.messages, msg];
        let title = c.title;
        if (c.messages.length === 1 && c.messages[0].role === 'bot') {
          title = msg.text.substring(0, 30) + (msg.text.length > 30 ? '...' : '');
        }
        return { ...c, messages: updatedMessages, title, updatedAt: new Date() };
      }
      return c;
    }));
  }

  private simulateResponse(query: string) {
    this.isTyping.set(true);
    
    const steps: ThinkingStep[] = [
      { label: 'Recherche dans la base de connaissance...', status: 'running' },
      { label: 'Croisement avec les textes de loi...', status: 'pending' },
      { label: 'Génération de la réponse finale...', status: 'pending' }
    ];

    const botMsgId = crypto.randomUUID();
    const botMsg: Message = {
      id: botMsgId,
      role: 'bot',
      text: '',
      timestamp: new Date(),
      thinkingSteps: this.agentModeEnabled() ? steps : undefined
    };

    this.updateMessages(botMsg);

    if (this.agentModeEnabled()) {
      this.runThinkingCycle(botMsgId, steps);
    } else {
      setTimeout(() => {
        this.finalizeBotMessage(botMsgId);
      }, 1500);
    }
  }

  private runThinkingCycle(msgId: string, steps: ThinkingStep[]) {
    setTimeout(() => {
      this.updateStep(msgId, 0, 'done');
      this.setStepRunning(msgId, 1);
      
      setTimeout(() => {
        this.updateStep(msgId, 1, 'done');
        this.setStepRunning(msgId, 2);
        
        setTimeout(() => {
          this.updateStep(msgId, 2, 'done');
          this.finalizeBotMessage(msgId);
        }, 1000);
      }, 1200);
    }, 1000);
  }

  private updateStep(msgId: string, stepIdx: number, status: 'pending' | 'running' | 'done') {
    this.conversations.update(prev => prev.map(c => {
      if (c.id === this.activeConversationId()) {
        const msgs = c.messages.map(m => {
          if (m.id === msgId && m.thinkingSteps) {
            const newSteps = [...m.thinkingSteps];
            newSteps[stepIdx] = { ...newSteps[stepIdx], status };
            return { ...m, thinkingSteps: newSteps };
          }
          return m;
        });
        return { ...c, messages: msgs };
      }
      return c;
    }));
  }

  private setStepRunning(msgId: string, stepIdx: number) {
    this.updateStep(msgId, stepIdx, 'running');
  }

  private finalizeBotMessage(msgId: string) {
    const responseText = "D'après les documents indexés, la Loi 103-13 (article 503-1-1) définit le harcèlement comme des actes, paroles ou gestes à caractère sexuel ou destinés à harceler la victime.";
    const sources: Source[] = [
      { name: 'Loi 103-13.pdf', score: 0.92 },
      { name: 'Guide_UNICEF_Signalement.docx', score: 0.78 }
    ];

    // Start streaming words
    let currentText = '';
    const words = responseText.split(' ');
    let i = 0;

    const interval = setInterval(() => {
      if (i < words.length) {
        currentText += (i === 0 ? '' : ' ') + words[i];
        this.updateBotText(msgId, currentText);
        this.scrollToBottom();
        i++;
      } else {
        clearInterval(interval);
        // Finalize with sources
        this.conversations.update(prev => prev.map(c => {
          if (c.id === this.activeConversationId()) {
            const msgs = c.messages.map(m => {
              if (m.id === msgId) {
                return { ...m, text: currentText, sources };
              }
              return m;
            });
            return { ...c, messages: msgs };
          }
          return c;
        }));
        this.isTyping.set(false);
        this.scrollToBottom();
      }
    }, 40);
  }

  private updateBotText(msgId: string, text: string) {
    this.conversations.update(prev => prev.map(c => {
      if (c.id === this.activeConversationId()) {
        const msgs = c.messages.map(m => {
          if (m.id === msgId) {
            return { ...m, text };
          }
          return m;
        });
        return { ...c, messages: msgs };
      }
      return c;
    }));
  }

  private scrollToBottom() {
    setTimeout(() => {
      const el = document.getElementById('chat-scroll-container');
      if (el) el.scrollTop = el.scrollHeight;
    }, 60);
  }

  getGroupedConversations() {
    const now = new Date();
    const today = this.conversations().filter(c => this.isSameDay(c.updatedAt, now));
    const yesterday = this.conversations().filter(c => this.isYesterday(c.updatedAt, now));
    const older = this.conversations().filter(c => !this.isSameDay(c.updatedAt, now) && !this.isYesterday(c.updatedAt, now));
    
    return [
      { label: 'Aujourd\'hui', chats: today },
      { label: 'Hier', chats: yesterday },
      { label: 'Anciens', chats: older }
    ].filter(g => g.chats.length > 0);
  }

  private isSameDay(d1: Date, d2: Date) {
    return d1.getFullYear() === d2.getFullYear() && d1.getMonth() === d2.getMonth() && d1.getDate() === d2.getDate();
  }

  private isYesterday(d1: Date, d2: Date) {
    const yesterday = new Date(d2);
    yesterday.setDate(yesterday.getDate() - 1);
    return this.isSameDay(d1, yesterday);
  }
}
