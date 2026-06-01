import { Component, signal, effect, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../../core/services/api.service';

export interface Source {
  name: string;
  score?: number;
  type?: string;
  url?: string;
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

export interface SuggestedQuestion {
  icon: string;
  text: string;
  category: string;
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
  
  conversations = signal<Conversation[]>([]);
  activeConversationId = signal<string>('');
  inputText = '';
  isTyping = signal(false);
  suggestedQuestions = signal<SuggestedQuestion[]>([]);

  activeConversation = signal<Conversation | undefined>(undefined);

  private apiService = inject(ApiService);

  constructor() {
    effect(() => {
      const conv = this.conversations().find(c => c.id === this.activeConversationId());
      this.activeConversation.set(conv);
    }, { allowSignalWrites: true });
  }

  ngOnInit() {
    this.loadSessions();
    this.loadSuggestedQuestions();
  }

  loadSessions() {
    this.apiService.getChatSessions().subscribe({
      next: (sessions) => {
        // Convert API dates back to Date objects
        const formattedSessions = sessions.map(s => ({
          ...s,
          updatedAt: new Date(s.updatedAt),
          messages: s.messages.map((m: any) => ({
            ...m,
            timestamp: new Date(m.timestamp)
          }))
        }));
        
        this.conversations.set(formattedSessions);
        if (formattedSessions.length > 0 && !this.activeConversationId()) {
          this.activeConversationId.set(formattedSessions[0].id);
        } else if (formattedSessions.length === 0) {
          this.newChat();
        }
      },
      error: (err) => console.error('Failed to load chat sessions', err)
    });
  }

  private getSystemLanguage(): 'fr' | 'ar' | 'en' {
    const lang = navigator.language.split('-')[0];
    if (['fr', 'ar', 'en'].includes(lang)) return lang as any;
    return 'fr';
  }

  loadSuggestedQuestions() {
    this.apiService.getSuggestedQuestions(this.activeLanguage()).subscribe({
      next: (questions) => this.suggestedQuestions.set(questions),
      error: (err) => console.error('Failed to load suggested questions', err)
    });
  }

  shouldShowSuggestions(): boolean {
    const conv = this.activeConversation();
    if (!conv) return true;
    // Show suggestions only when there's just the welcome message (or no messages)
    const userMessages = conv.messages.filter(m => m.role === 'user');
    return userMessages.length === 0;
  }

  askSuggested(question: string) {
    if (this.isTyping()) return;
    this.inputText = question;
    this.sendMessage();
  }

  selectConversation(id: string) {
    this.activeConversationId.set(id);
  }

  newChat() {
    const newConv: Conversation = {
      id: 'temp-' + Math.random().toString(36).substring(7),
      title: 'Nouvelle conversation',
      messages: [],
      updatedAt: new Date()
    };
    
    this.conversations.update(prev => [newConv, ...prev]);
    this.activeConversationId.set(newConv.id);
  }

  deleteConversation(id: string, event?: Event) {
    if (event) event.stopPropagation();
    
    // Optimistically update UI
    this.conversations.update(prev => prev.filter(c => c.id !== id));
    
    // If we deleted the active conversation, switch to the first available one or create new
    if (this.activeConversationId() === id) {
      const remaining = this.conversations();
      if (remaining.length > 0) {
        this.activeConversationId.set(remaining[0].id);
      } else {
        this.activeConversationId.set('');
        this.newChat();
      }
    }

    // Call API (only if it's a real UUID from the backend, not a temporary new chat ID)
    if (!id.startsWith('temp-')) {
      this.apiService.deleteChatSession(id).subscribe({
        error: (err) => console.error('Failed to delete session', err)
      });
    }
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
        if (c.title === 'Nouvelle conversation' && msg.role === 'user') {
          title = msg.text.substring(0, 30) + (msg.text.length > 30 ? '...' : '');
        }
        return { ...c, messages: updatedMessages, title, updatedAt: new Date() };
      }
      return c;
    }));
  }

  private simulateResponse(query: string) {
    this.isTyping.set(true);
    
    // Default fallback steps
    let steps: ThinkingStep[] = [
      { label: 'Recherche dans la base de connaissance...', status: 'running' }
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

    // A real UUID from the backend is 36 characters. The temporary ID we generate is ~6-7 chars.
    const currentId = this.activeConversationId();
    const isNewSession = currentId.length < 20; 
    const sessionId = isNewSession ? undefined : currentId;
    
    // Call the actual API
    this.apiService.askChatbot(query, sessionId, this.activeLanguage()).subscribe({
      next: (res) => {
        // Only update session ID if it was a new session (and we just got a real UUID)
        if (isNewSession && res.session_id) {
            this.conversations.update(prev => prev.map(c => 
                c.id === this.activeConversationId() ? { ...c, id: res.session_id } : c
            ));
            this.activeConversationId.set(res.session_id);
        }

        // Use backend thinking steps if provided, else keep default
        if (res.thinking_steps && this.agentModeEnabled()) {
           this.conversations.update(prev => prev.map(c => {
             if (c.id === this.activeConversationId()) {
               return {
                 ...c,
                 messages: c.messages.map(m => m.id === botMsgId ? {...m, thinkingSteps: res.thinking_steps} : m)
               };
             }
             return c;
           }));
        }

        this.finalizeBotMessage(botMsgId, res.answer, res.sources);
      },
      error: (err) => {
        console.error(err);
        this.finalizeBotMessage(botMsgId, "Erreur de connexion au serveur RAG. Veuillez réessayer.", []);
      }
    });
  }

  private finalizeBotMessage(msgId: string, responseText: string, sources: Source[]) {

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
